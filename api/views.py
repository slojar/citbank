import decimal
from threading import Thread

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status, views

from account.models import Customer, Transaction, AccountRequest
from account.serializers import CustomerSerializer, TransferSerializer, AccountRequestSerializer
from account.paginations import CustomPagination
from account.utils import review_account_request, log_request, format_phone_number, dashboard_transaction_data
from bankone.api import bankone_send_otp_message, bankone_check_phone_no
from billpayment.models import Airtime, CableTV, Data, Electricity
from billpayment.serializers import AirtimeSerializer, DataSerializer, CableTVSerializer, ElectricitySerializer
from citbank.exceptions import raise_serializer_error_msg
from coporate.models import Institution, Mandate
from coporate.serializers import MandateSerializerIn, InstitutionSerializerIn, InstitutionSerializerOut, \
    MandateSerializerOut


class Homepage(views.APIView):
    # permission_classes = [IsAdminUser]
    permission_classes = []

    def get(self, request):
        bank = request.GET.get("bank_id")
        if not bank:
            return Response({"detail": "Bank ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        data = dict()

        customer_queryset = Customer.objects.filter(bank_id=bank)
        institution_query = Institution.objects.filter(bank_id=bank)
        transaction_queryset = Transaction.objects.filter(customer__bank_id=bank, status="success")
        airtime_queryset = Airtime.objects.filter(bank_id=bank)
        data_queryset = Data.objects.filter(bank_id=bank)
        cable_tv_queryset = CableTV.objects.filter(bank_id=bank)
        electricity_queryset = Electricity.objects.filter(bank_id=bank)
        account_request_queryset = \
            AccountRequest.objects.filter(bank_id=bank, status="pending").order_by("-created_on")[:10]

        # Get counts and aggregates
        total_individual_customer = customer_queryset.count()
        total_active_individual_customer = customer_queryset.filter(active=True).count()
        total_inactive_individual_customer = customer_queryset.filter(active=False).count()

        total_institutions = institution_query.count()
        total_active_institution = institution_query.filter(active=True).count()
        total_inactive_institution = institution_query.filter(active=False).count()
        # recent = account_request_queryset.values_list(get_request_detail(), flat=True)
        recent = [item.get_request_detail() for item in account_request_queryset]
        airtime_count = airtime_queryset.count()
        data_count = data_queryset.count()
        cable_tv_count = cable_tv_queryset.count()
        electricity_count = electricity_queryset.count()
        transfer_count = transaction_queryset.count()
        airtime_purchase_total = airtime_queryset.filter(
            status__iexact="success").aggregate(Sum("amount"))["amount__sum"] or 0
        data_purchase_total = data_queryset.filter(
            status__iexact="success").aggregate(Sum("amount"))["amount__sum"] or 0
        cable_tv_purchase_total = cable_tv_queryset.filter(
            status__iexact="success").aggregate(Sum("amount"))["amount__sum"] or 0
        electricity_purchase_total = electricity_queryset.filter(
            status__iexact="success").aggregate(Sum("amount"))["amount__sum"] or 0
        transfer_total = transaction_queryset.aggregate(Sum("amount"))["amount__sum"] or 0

        ind_airtime_purchase = airtime_queryset.filter(status__iexact="success", institution__isnull=True)
        ind_data_purchase = data_queryset.filter(status__iexact="success", institution__isnull=True)
        ind_cable_tv_purchase = cable_tv_queryset.filter(status__iexact="success", institution__isnull=True)
        ind_electricity_purchase = electricity_queryset.filter(status__iexact="success", institution__isnull=True)
        ind_transfer = transaction_queryset.filter(customer__isnull=False)
        corp_airtime_purchase = airtime_queryset.filter(status__iexact="success", institution__isnull=False)
        corp_data_purchase = data_queryset.filter(status__iexact="success", institution__isnull=False)
        corp_cable_tv_purchase = cable_tv_queryset.filter(status__iexact="success", institution__isnull=False)
        corp_transfer = transaction_queryset.filter(status__iexact="success", institution__isnull=False)
        corp_electricity_purchase = electricity_queryset.filter(status__iexact="success", institution__isnull=False)

        ind_airtime_purchase_total = ind_airtime_purchase.aggregate(Sum("amount"))["amount__sum"] or 0
        ind_data_purchase_total = ind_data_purchase.aggregate(Sum("amount"))["amount__sum"] or 0
        ind_cable_tv_purchase_total = ind_cable_tv_purchase.aggregate(Sum("amount"))["amount__sum"] or 0
        ind_electricity_purchase_total = ind_electricity_purchase.aggregate(Sum("amount"))["amount__sum"] or 0
        ind_transfer_total = ind_transfer.aggregate(Sum("amount"))["amount__sum"] or 0
        corp_airtime_purchase_total = corp_airtime_purchase.aggregate(Sum("amount"))["amount__sum"] or 0
        corp_data_purchase_total = corp_data_purchase.aggregate(Sum("amount"))["amount__sum"] or 0
        corp_cable_tv_purchase_total = corp_cable_tv_purchase.aggregate(Sum("amount"))["amount__sum"] or 0
        corp_transfer_total = corp_transfer.aggregate(Sum("amount"))["amount__sum"] or 0
        corp_electricity_purchase_total = corp_electricity_purchase.aggregate(Sum("amount"))["amount__sum"] or 0

        ind_airtime_purchase_count = ind_airtime_purchase.count()
        ind_data_purchase_count = ind_data_purchase.count()
        ind_cable_tv_purchase_count = ind_cable_tv_purchase.count()
        ind_electricity_purchase_count = ind_electricity_purchase.count()
        ind_transfer_count = ind_transfer.count()
        corp_airtime_purchase_count = corp_airtime_purchase.count()
        corp_data_purchase_count = corp_data_purchase.count()
        corp_cable_tv_purchase_count = corp_cable_tv_purchase.count()
        corp_transfer_count = corp_transfer.count()
        corp_electricity_purchase_count = corp_electricity_purchase.count()

        data["recent_customer"] = recent
        data["total_customer_count"] = total_individual_customer + total_institutions
        data["total_individual_customer_count"] = total_individual_customer
        data["total_corporate_customer_count"] = total_institutions
        data["total_active_individual_customer_count"] = total_active_individual_customer
        data["total_inactive_individual_customer_count"] = total_inactive_individual_customer
        data["total_active_corporate_customer_count"] = total_active_institution
        data["total_inactive_corporate_customer_count"] = total_inactive_institution

        data["airtime_count"] = airtime_count
        data["data_count"] = data_count
        data["cable_tv_count"] = cable_tv_count
        data["electricity_count"] = electricity_count
        data["airtime_purchase_total"] = airtime_purchase_total
        data["data_purchase_total"] = data_purchase_total
        data["cable_tv_purchase_total"] = cable_tv_purchase_total
        data["electricity_purchase_total"] = electricity_purchase_total

        data["total_bill_payment_amount"] = \
            airtime_purchase_total + data_purchase_total + cable_tv_purchase_total + electricity_purchase_total
        data["total_bill_payment_count"] = airtime_count + data_count + cable_tv_count + electricity_count
        data["total_transaction_count"] = \
            airtime_count + data_count + cable_tv_count + transfer_count + electricity_count
        data["total_transaction_amount"] = airtime_purchase_total + data_purchase_total + cable_tv_purchase_total + decimal.Decimal(transfer_total) + electricity_purchase_total

        data["total_individual_transaction_amount"] = ind_airtime_purchase_total + ind_data_purchase_total + ind_cable_tv_purchase_total + decimal.Decimal(ind_transfer_total) + ind_electricity_purchase_total
        data["total_individual_transaction_count"] = ind_airtime_purchase_count + ind_data_purchase_count + ind_cable_tv_purchase_count + decimal.Decimal(ind_transfer_count) + ind_electricity_purchase_count
        data["total_corporate_transaction_amount"] = corp_airtime_purchase_total + corp_data_purchase_total + corp_cable_tv_purchase_total + decimal.Decimal(corp_transfer_total) + corp_electricity_purchase_total
        data["total_corporate_transaction_count"] = corp_airtime_purchase_count + corp_data_purchase_count + corp_cable_tv_purchase_count + decimal.Decimal(corp_transfer_count) + corp_electricity_purchase_count

        data["local_transfer_chart"] = dashboard_transaction_data(bank, "local")
        data["others_transfer_chart"] = dashboard_transaction_data(bank, "others")

        return Response(data)


class AdminCustomerAPIView(views.APIView, CustomPagination):
    permission_classes = [IsAdminUser]

    def get(self, request, bank_id, pk=None):
        if pk:
            customer = get_object_or_404(Customer, id=pk, bank_id=bank_id)
            # data = CustomerSerializer(Customer.objects.get(id=pk, bank_id=bank_id), context={'request': request}).data
            data = CustomerSerializer(customer, context={'request': request}).data
        else:
            search = request.GET.get("search")
            account_status = request.GET.get("account_status")

            query = Q(bank_id=bank_id)
            if search:
                query &= Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search) | \
                         Q(user__email__icontains=search) | Q(customerID__exact=search) | \
                         Q(user__username__icontains=search) | Q(customeraccount__account_no__exact=search) | \
                         Q(phone_number__exact=search)

                customers = Customer.objects.filter(query).order_by('-created_on').distinct()
            elif account_status:
                query &= Q(active=account_status)

                customers = Customer.objects.filter(query).order_by('-created_on').distinct()
            else:
                customers = Customer.objects.filter(query).order_by('-created_on')

            result = self.paginate_queryset(customers, request)
            serializer = CustomerSerializer(result, many=True, context={'request': request}).data
            data = self.get_paginated_response(serializer).data

        return Response(data)

    def put(self, request, bank_id, pk):

        account_status = request.data.get("is_active")
        staff_status = request.data.get("staff_status")
        daily_limit = request.data.get("daily_limit")
        transfer_limit = request.data.get("transfer_limit")
        phone_number = request.data.get("phone_number")
        try:
            customer = get_object_or_404(Customer, id=pk, bank_id=bank_id)
            if account_status is True:
                customer.active = True
            if account_status is False:
                customer.active = False
            if daily_limit:
                customer.daily_limit = daily_limit
            if transfer_limit:
                customer.transfer_limit = transfer_limit
            if staff_status is True:
                customer.user.is_staff = True
            if staff_status is False:
                customer.user.is_staff = False
            if phone_number:
                # Confirm phone number exist
                phone_no = format_phone_number(phone_number)
                customer.phone_number = phone_no if bankone_check_phone_no else None
            customer.user.save()
            customer.save()
        except Exception as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Account updated successfully"})


class AdminTransferAPIView(views.APIView, CustomPagination):
    permission_classes = []

    def get(self, request, bank_id):
        transfer_type = request.GET.get("transfer_type")  # local, others
        search = request.GET.get("search")

        query = Q(customer__bank_id=bank_id)
        if search:
            query &= Q(customer__user__first_name__iexact=search) | Q(customer__user__last_name__iexact=search) | \
                     Q(customer__customerID=search) | Q(beneficiary_name__icontains=search) | \
                     Q(reference__iexact=search)

        if transfer_type == "local":
            query &= Q(transfer_type="local_transfer") | Q(transfer_type="transfer")
            transfers = Transaction.objects.filter(query).order_by('-created_on').distinct()
        elif transfer_type == "others":
            query &= Q(transfer_type="external_transfer")
            transfers = Transaction.objects.filter(query).order_by('-created_on').distinct()
        else:
            transfers = Transaction.objects.filter(query).order_by('-created_on')

        queryset = self.paginate_queryset(transfers, request)
        serializer = TransferSerializer(queryset, many=True).data
        data = self.get_paginated_response(serializer).data

        return Response(data)


class AdminBillPaymentAPIView(views.APIView, CustomPagination):
    permission_classes = []

    def get(self, request, bank_id):

        bill_type = request.GET.get("bill_type")
        search = request.GET.get("search")

        data = dict()

        query = Q(bank_id=bank_id)

        if not bill_type:
            return Response({"detail": "Bill type is required"}, status=status.HTTP_400_BAD_REQUEST)

        if bill_type == "airtime":
            if search:
                query &= Q(account_no__iexact=search) | Q(beneficiary__iexact=search) | Q(network__iexact=search) | \
                         Q(transaction_id__iexact=search)
                queryset = Airtime.objects.filter(query).distinct().order_by('-created_on')
            else:
                queryset = Airtime.objects.filter(bank_id=bank_id).order_by('-created_on')
            queryset = self.paginate_queryset(queryset, request)
            serializer = AirtimeSerializer(queryset, many=True).data

        elif bill_type == "data":
            if search:
                query &= Q(account_no__iexact=search) | Q(beneficiary__iexact=search) | Q(network__iexact=search) | \
                         Q(transaction_id__iexact=search) | Q(plan_id__iexact=search)
                queryset = Data.objects.filter(query).distinct().order_by('-created_on')
            else:
                queryset = Data.objects.filter(bank_id=bank_id).order_by('-created_on')
            queryset = self.paginate_queryset(queryset, request)
            serializer = DataSerializer(queryset, many=True).data

        elif bill_type == "cable_tv":
            if search:
                query &= Q(account_no__iexact=search) | Q(service_name__iexact=search) | \
                         Q(smart_card_no__iexact=search) | Q(transaction_id__iexact=search) | \
                         Q(phone_number__iexact=search)
                queryset = CableTV.objects.filter(query).distinct().order_by('-created_on')
            else:
                queryset = CableTV.objects.filter(bank_id=bank_id).order_by('-created_on')
            queryset = self.paginate_queryset(queryset, request)
            serializer = CableTVSerializer(queryset, many=True).data

        elif bill_type == "electricity":
            if search:
                query &= Q(account_no__iexact=search) | Q(disco_type__iexact=search) | \
                         Q(meter_number__iexact=search) | Q(transaction_id__iexact=search) | \
                         Q(phone_number__iexact=search)
                queryset = Electricity.objects.filter(query).distinct().order_by('-created_on')
            else:
                queryset = Electricity.objects.filter(bank_id=bank_id).order_by('-created_on')
            queryset = self.paginate_queryset(queryset, request)
            serializer = ElectricitySerializer(queryset, many=True).data

        else:
            return Response({"detail": "Invalid bill type selected"}, status=status.HTTP_400_BAD_REQUEST)

        detail = self.get_paginated_response(serializer).data
        data["detail"] = detail

        return Response(data)


class AdminAccountRequestAPIView(views.APIView, CustomPagination):
    permission_classes = [IsAdminUser]

    def get(self, request, bank_id, pk=None):
        if pk:
            acct_req = get_object_or_404(AccountRequest, bank_id=bank_id, id=pk)
            result = AccountRequestSerializer(acct_req, context={"request": request}).data
        else:
            req_status = request.GET.get("status")
            if req_status:
                queryset = AccountRequest.objects.filter(bank_id=bank_id, status=req_status).order_by("-created_on")
            else:
                queryset = AccountRequest.objects.filter(bank_id=bank_id).order_by("-created_on")

            req = self.paginate_queryset(queryset, request)
            serializer = AccountRequestSerializer(req, many=True, context={"request": request}).data
            result = self.get_paginated_response(serializer).data
        return Response(result)

    def put(self, request, bank_id, pk):
        req_status = request.data.get("status")
        reason = request.data.get("rejection_reason")

        acct_req = get_object_or_404(AccountRequest, bank_id=bank_id, id=pk)

        if not (req_status == "approved" or req_status == "declined"):
            return Response({"detail": f"{req_status} is not a valid status"}, status=status.HTTP_400_BAD_REQUEST)

        if req_status == "declined":
            if not reason:
                return Response({"detail": "Kindly fill why you are rejecting this application"},
                                status=status.HTTP_400_BAD_REQUEST)
            acct_req.rejection_reason = reason
            acct_req.rejected_by = request.user
            # Send rejection email to the customer
            content = f"Dear {acct_req.first_name}, \nYour account opening is declined, " \
                      f"a customer service agent will contact you soon."
            subject = f"{acct_req.bank.name}: Account Creation Rejected"
            Thread(
                target=bankone_send_otp_message,
                args=[acct_req.phone_no, content, subject, 1234567890, acct_req.email, acct_req.bank]
            ).start()

        if req_status == "approved":
            acct_req.approved_by = request.user
            success, detail = review_account_request(acct_req)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        acct_req.status = req_status
        acct_req.save()
        return Response({
            "detail": "Request Submitted", "data": AccountRequestSerializer(acct_req, context={"request": request}).data
        })


class CorporateUserAPIView(views.APIView, CustomPagination):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = MandateSerializerIn(data=request.data, context={"request": request})
        serializer.is_valid() or raise_serializer_error_msg(errors=serializer.errors)
        response = serializer.save()
        return Response({"detail": "Mandate added successfully", "data": response})

    def get(self, request, pk=None):
        admin_bank = request.user.customer.bank
        if pk:
            mandate = get_object_or_404(Mandate, id=pk, institution__bank=admin_bank)
            return Response(MandateSerializerOut(mandate).data)
        queryset = self.paginate_queryset(Mandate.objects.filter(institution__bank=admin_bank).order_by("-id"), request)
        serializer = MandateSerializerOut(queryset, many=True).data
        return Response(self.get_paginated_response(serializer).data)

    def put(self, request, pk):
        try:
            mandate_status = request.data.get("active", bool)
        except Exception as err:
            log_request(err)
            return Response({"detail": "Active status is either True or False"}, status=status.HTTP_400_BAD_REQUEST)
        admin_bank = request.user.customer.bank
        mandate = get_object_or_404(Mandate, id=pk, institution__bank=admin_bank)
        mandate.active = mandate_status
        mandate.save()
        serializer = MandateSerializerOut(mandate, context={"request": request}).data
        return Response({"detail": "Mandate status changed successfully", "data": serializer})


class InstitutionAPIView(views.APIView, CustomPagination):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = InstitutionSerializerIn(data=request.data, context={"request": request})
        serializer.is_valid() or raise_serializer_error_msg(errors=serializer.errors)
        response = serializer.save()
        return Response({"detail": "Institution created successfully", "data": response})

    def get(self, request, pk=None):
        bank = request.user.customer.bank
        if pk:
            inst = get_object_or_404(Institution, id=pk, bank=bank)
            return Response(InstitutionSerializerOut(inst).data)
        queryset = self.paginate_queryset(Institution.objects.filter(bank=bank).order_by("-id"), request)
        serializer = InstitutionSerializerOut(queryset, many=True).data
        return Response(self.get_paginated_response(serializer).data)


# class CorporateRoleListAPIView(generics.ListAPIView):
#     permission_classes = [IsAdminUser]
#     queryset = Role.objects.all().order_by("-id")
#     serializer_class = RoleSerializerOut
