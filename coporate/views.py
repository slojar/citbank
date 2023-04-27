import json

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from account.paginations import CustomPagination
from account.utils import get_account_officer, log_request, get_account_balance
from billpayment.models import Airtime, Data, CableTV, Electricity, BulkBillPayment
from citbank.exceptions import raise_serializer_error_msg, InvalidRequestException
from coporate.cron import transfer_scheduler_job, delete_uploaded_files
from coporate.models import Mandate, TransferRequest, TransferScheduler, BulkTransferRequest
from coporate.permissions import IsUploader, IsMandate
from coporate.serializers import MandateSerializerOut, LimitSerializerOut, TransferRequestSerializerOut, \
    TransferRequestSerializerIn, TransferSchedulerSerializerOut, BulkUploadFileSerializerIn, BulkTransferSerializerIn, \
    BulkTransferSerializerOut, BulkUploadBillSerializerIn, BulkPaymentSerializerOut
from coporate.utils import get_dashboard_data, check_mandate_password_pin_otp, \
    update_transaction_limits, verify_approve_transfer, generate_and_send_otp, change_password, \
    check_balance_for_bill_payment, create_bill_payment, retrieve_bill_payment, verify_approve_bill_payment

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


class MandateLoginAPIView(APIView):
    permission_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        customer_id = request.data.get("customer_id")

        if not all([username, password, customer_id]):
            raise InvalidRequestException({"detail": "Username, customerID, and password required"})

        # Check user is valid
        user = authenticate(request, username=username, password=password)

        if not user:
            raise InvalidRequestException({"detail": "Invalid username or password"})

        mandate = get_object_or_404(Mandate, user=user)
        if mandate.institution.customerID != customer_id:
            return Response({"detail": "Invalid Customer ID"})
        check_mandate_password_pin_otp(mandate, active=1)
        data = get_account_balance(mandate.institution, "corporate")
        data.update({"mandate": MandateSerializerOut(mandate, context={"request": request}).data})
        return Response({
            "detail": "Login Successful", "access_token": str(AccessToken.for_user(user)),
            "refresh_token": str(RefreshToken.for_user(user)), "data": data
        })


class MandateDashboardAPIView(APIView):
    permission_classes = [IsMandate]

    def get(self, request):
        mandate = get_object_or_404(Mandate, user=request.user)
        data = get_dashboard_data(mandate)
        return Response({"detail": "Data retrieved", "data": data})


class InstitutionAccountOfficer(APIView):
    permission_classes = [IsMandate]

    def get(self, request):
        mandate = get_object_or_404(Mandate, user=request.user)
        account = mandate.institution
        bank = account.bank
        data = get_account_officer(account, bank)
        return Response({"detail": "Account Officer retrieved", "data": data})


class TransferLimitAPIView(APIView):
    permission_classes = [IsMandate]

    def put(self, request):
        otp = request.data.get("otp")
        mandate = get_object_or_404(Mandate, user=request.user)
        # Check otp is valid
        if not otp:
            return Response({"detail": "Token is required to continue"}, status=status.HTTP_400_BAD_REQUEST)
        check_mandate_password_pin_otp(mandate, otp=otp)
        limit = update_transaction_limits(request, mandate)
        data = LimitSerializerOut(limit, context={"request": request}).data
        return Response({"detail": "Transaction Limit updated successfully", "data": data})


class TransferRequestAPIView(APIView, CustomPagination):
    permission_classes = [IsMandate]

    def get(self, request, pk=None):
        mandate = get_object_or_404(Mandate, user=request.user)
        if pk:
            req = get_object_or_404(TransferRequest, id=pk, institution=mandate.institution, transfer_option="single")
            data = TransferRequestSerializerOut(req, context={"request": request}).data
        else:
            approval_status = request.GET.get("status")  # checked, verified, approved
            date_from = request.GET.get("date_from")
            date_to = request.GET.get("date_to")
            search = request.GET.get("search")

            query = Q(institution=mandate.institution, transfer_option="single")
            if search:
                query &= Q(account_number__iexact=search) | Q(beneficiary_acct__iexact=search) | \
                         Q(bank_name__iexact=search) | Q(transfer_type__iexact=search) | Q(
                    beneficiary_acct_type__iexact=search)
            if date_from and date_to:
                query &= Q(created_on__range=[date_from, date_to])
            if approval_status:
                if approval_status == "checked":
                    query &= Q(checked=True)
                if approval_status == "verified":
                    query &= Q(verified=True)
                if approval_status == "approved":
                    query &= Q(approved=True)

            queryset = self.paginate_queryset(TransferRequest.objects.filter(query), request)
            serializer = TransferRequestSerializerOut(queryset, many=True, context={"request": request}).data
            data = self.get_paginated_response(serializer).data
        return Response(data)

    def post(self, request):
        serializer = TransferRequestSerializerIn(data=request.data, context={"request": request})
        serializer.is_valid() or raise_serializer_error_msg(errors=serializer.errors)
        response = serializer.save()
        return Response({"detail": "Transfer request created successfully", "data": response})

    def put(self, request, pk):
        otp = request.data.get("otp")
        action = request.data.get("action")
        request_type = request.data.get("transfer_type", "single")  # single or bulk
        reject_reason = request.data.get("reason")
        accepted_action = ["approve", "decline"]

        mandate = get_object_or_404(Mandate, user=request.user)
        check_mandate_password_pin_otp(mandate, otp=otp)

        if mandate.level != 1:
            if action not in accepted_action:
                return Response({"detail": "Selected action is not valid"}, status=status.HTTP_400_BAD_REQUEST)

            if action == "decline" and not reject_reason:
                return Response({"detail": "Rejection reason is required"}, status=status.HTTP_400_BAD_REQUEST)

        if request_type == "single":
            trans_req = get_object_or_404(TransferRequest, id=pk, institution=mandate.institution,
                                          transfer_option="single")
            trans_request = verify_approve_transfer(request, trans_req, mandate, request_type, action, reject_reason)
            serializer = TransferRequestSerializerOut(trans_request, context={"request": request}).data
        elif request_type == "bulk":
            trans_req = get_object_or_404(BulkTransferRequest, id=pk, institution=mandate.institution)
            trans_request = verify_approve_transfer(request, trans_req, mandate, request_type, action, reject_reason)
            serializer = BulkTransferSerializerOut(trans_request, context={"request": request}).data
        else:
            return Response({"detail": "Transfer type can either be single or bulk"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Transfer updated successfully", "data": serializer})


class SendOTPAPIView(APIView):
    permission_classes = [IsMandate]

    def get(self, request):
        mandate = get_object_or_404(Mandate, user=request.user)
        token = generate_and_send_otp(mandate)
        return Response({"detail": "Token has been sent to your email", "otp": token})


class MandateChangePasswordAPIView(APIView):
    permission_classes = [IsMandate]
    def post(self, request):
        otp = request.data.get("otp")
        if not otp:
            return Response({"detail": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)
        mandate = get_object_or_404(Mandate, user=request.user)
        check_mandate_password_pin_otp(mandate, otp=otp)
        change_password(mandate, data=request.data)
        return Response({"detail": "Password changed successfully"})


class TransferSchedulerAPIView(APIView, CustomPagination):
    permission_classes = [IsMandate]
    def get(self, request, pk=None):
        result = list()
        mandate = get_object_or_404(Mandate, user=request.user)
        if pk:
            if not TransferRequest.objects.filter(scheduler_id=pk, institution=mandate.institution).exists():
                return Response({"detail": "Selected scheduler is not valid"}, status=status.HTTP_400_BAD_REQUEST)
            data = TransferSchedulerSerializerOut(TransferScheduler.objects.get(id=pk)).data
        else:
            status_query = request.GET.get("status")
            query = Q(institution=mandate.institution, scheduled=True)
            if status_query:
                query &= Q(status=status_query)
            transfer_request = TransferRequest.objects.filter(query)
            schedulers = [transfer.scheduler for transfer in transfer_request]
            for item in schedulers:
                if item not in result:
                    result.append(item)
            queryset = self.paginate_queryset(result, request)
            serializer = TransferSchedulerSerializerOut(queryset, many=True).data
            data = self.get_paginated_response(serializer).data
        return Response(data)

    def put(self, request, pk):
        update_status = request.data.get("status")
        mandate = get_object_or_404(Mandate, user=request.user)
        if not update_status or (update_status != "active" and update_status != "inactive"):
            return Response({"detail": "Kindly select a valid status"}, status=status.HTTP_400_BAD_REQUEST)
        if not TransferRequest.objects.filter(scheduler_id=pk, institution=mandate.institution).exists():
            return Response({"detail": "Selected scheduler is not valid"}, status=status.HTTP_400_BAD_REQUEST)

        scheduler = TransferScheduler.objects.get(id=pk)
        scheduler.status = update_status
        scheduler.save()
        data = TransferSchedulerSerializerOut(scheduler).data
        return Response({"detail": "Scheduler status changed successfully", "data": data})


class BulkUploadAPIView(APIView):
    permission_classes = [IsUploader]

    def post(self, request):
        serializer = BulkUploadFileSerializerIn(data=request.data, context={"request": request})
        serializer.is_valid() or raise_serializer_error_msg(errors=serializer.errors)
        response = serializer.save()
        return Response({"detail": "File uploaded successfully", "data": response})


class BulkTransferAPIView(APIView, CustomPagination):
    permission_classes = [IsMandate]

    def get(self, request, pk=None):
        mandate = get_object_or_404(Mandate, user=request.user)
        if pk:
            req = get_object_or_404(BulkTransferRequest, id=pk, institution=mandate.institution)
            data = BulkTransferSerializerOut(req, context={"request": request}).data
        else:
            date_from = request.GET.get("date_from")
            approval_status = request.GET.get("status")  # checked, verified, approved
            date_to = request.GET.get("date_to")

            query = Q(institution=mandate.institution)

            if date_from and date_to:
                query &= Q(created_on__range=[date_from, date_to])
            if approval_status:
                if approval_status == "checked":
                    query &= Q(checked=True)
                if approval_status == "verified":
                    query &= Q(verified=True)
                if approval_status == "approved":
                    query &= Q(approved=True)

            queryset = self.paginate_queryset(BulkTransferRequest.objects.filter(query), request)
            serializer = BulkTransferSerializerOut(queryset, many=True, context={"request": request}).data
            data = self.get_paginated_response(serializer).data
        return Response(data)

    def post(self, request):
        serializer = BulkTransferSerializerIn(data=request.data, context={"request": request})
        serializer.is_valid() or raise_serializer_error_msg(errors=serializer.errors)
        response = serializer.save()
        return Response({"detail": "Bulk Transfer saved successfully", "data": response})


class CorporateBillPaymentAPIView(APIView, CustomPagination):
    permission_classes = [IsMandate]

    def get(self, request, pk=None):
        mandate = get_object_or_404(Mandate, user=request.user)
        payment_type = request.GET.get("payment_type")
        bulk_payment = request.GET.get("bill_option")
        data = retrieve_bill_payment(self, payment_type, mandate.institution, bulk_payment, pk)
        return Response(data)

    def post(self, request):
        phone_number = request.data.get("phone_number")
        amount = request.data.get("amount")
        account_no = request.data.get("account_no")
        payment_type = request.data.get("payment_type")  # airtime, data, cable_tv, electricity

        mandate = get_object_or_404(Mandate, user=request.user)
        if mandate.level != 1:
            return Response({"detail": "You are not permitted to perform this action"})

        if not all([phone_number, amount, payment_type, account_no]):
            log_request(f"error-message: source account, phone number, amount, and payment type are required fields")
            return Response(
                {"detail": "source account, phone number, payment type, and amount are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        institution = mandate.institution

        success, message, ref_no = check_balance_for_bill_payment(institution, account_no, amount, payment_type)
        if success is False:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = create_bill_payment(request.data, account_no, phone_number, amount, payment_type, institution, ref_no)

        return Response({"detail": "Payment created successfully", "data": serializer})

    def put(self, request, pk):
        action = request.data.get("action")
        otp = request.data.get("otp")
        reject_reason = request.data.get("reason")
        accepted_action = ["approve", "decline"]
        payment_type = request.data.get("payment_type", "airtime")  # airtime, data, electricity, cable_tv
        bill_type = request.data.get("bill_option", "single")  # single or bulk

        mandate = get_object_or_404(Mandate, user=request.user)
        check_mandate_password_pin_otp(mandate, otp=otp)

        if mandate.level != 1:
            if action not in accepted_action:
                return Response({"detail": "Selected action is not valid"}, status=status.HTTP_400_BAD_REQUEST)

            if action == "decline" and not reject_reason:
                return Response({"detail": "Rejection reason is required"}, status=status.HTTP_400_BAD_REQUEST)

        if bill_type == "single":
            payment = None
            if payment_type == "airtime":
                payment = get_object_or_404(Airtime, id=pk, institution=mandate.institution, transaction_option="single")
            if payment_type == "data":
                payment = get_object_or_404(Data, id=pk, institution=mandate.institution, transaction_option="single")
            if payment_type == "cable_tv":
                payment = get_object_or_404(CableTV, id=pk, institution=mandate.institution, transaction_option="single")
            if payment_type == "electricity":
                payment = get_object_or_404(Electricity, id=pk, institution=mandate.institution, transaction_option="single")

            verify_approve_bill_payment(payment, mandate, bill_type, action, reject_reason)
        elif bill_type == "bulk":
            payment = get_object_or_404(BulkBillPayment, id=pk, institution=mandate.institution)
            verify_approve_bill_payment(payment, mandate, bill_type, action, reject_reason)
        else:
            return Response({"detail": "Bill type can either be single or bulk"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Bill payment updated successfully"})


class BulkBillPaymentAPIView(APIView, CustomPagination):
    permission_classes = [IsMandate]

    def get(self, request, pk=None):
        mandate = get_object_or_404(Mandate, user=request.user)
        if pk:
            payment = get_object_or_404(BulkBillPayment, id=pk, institution=mandate.institution)
            return BulkPaymentSerializerOut(payment).data
        else:
            queryset = self.paginate_queryset(BulkBillPayment.objects.filter(institution=mandate.institution), request)
            serializer = BulkTransferSerializerOut(queryset, many=True).data
            return self.get_paginated_response(serializer).data

    def post(self, request):
        if Mandate.objects.get(level__gt=1):
            return Response(
                {"detail": "Only lowest level signatory can perform this action"}, status=status.HTTP_400_BAD_REQUEST
            )
        serializer = BulkUploadBillSerializerIn(data=request.data, context={"request": request})
        serializer.is_valid() or raise_serializer_error_msg(errors=serializer.errors)
        response = serializer.save()
        return Response({"detail": "Bulk Payments saved successfully", "data": response})


# CRON-JOBs
class TransferRequestCronView(APIView):
    permission_classes = []

    def get(self, request):
        response = transfer_scheduler_job(request)
        return Response({"detail": response})


class DeleteUploadedFiles(APIView):
    permission_classes = []

    def get(self, request):
        response = delete_uploaded_files()
        return Response({"detail": response})
