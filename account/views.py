import json
import uuid
import requests
from threading import Thread

from django.db.models import Q
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponse

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .paginations import CustomPagination
from .serializers import CustomerSerializer, TransactionSerializer, BeneficiarySerializer, BankSerializer
from .utils import authenticate_user, generate_new_otp, \
    decrypt_text, encrypt_text, create_transaction, confirm_trans_pin

from bankone.api import get_account_by_account_no, log_request, send_otp_message, \
    cit_create_new_customer, generate_random_ref_code, send_email, get_details_by_customer_id
from .models import CustomerAccount, Customer, CustomerOTP, Transaction, Beneficiary, Bank

bankOneToken = settings.BANK_ONE_AUTH_TOKEN


class HomepageView(APIView):
    permission_classes = []
    def get(self, request):
        return HttpResponse("<h1>Welcome to CIT MFB User Management</h1>")


class RerouteView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            url = request.data.get("url", "")
            verb = request.data.get("method", "GET")
            header = request.data.get("header", {})
            payload = request.data.get("payload", {})

            header = json.dumps(header)
            payload = json.dumps(payload)

            response = {}

            if str("live_token") in url:
                url = str(url).replace("live_token", bankOneToken)
            if str("live_token") in header:
                header = str(header).replace("live_token", bankOneToken)
            if str("live_token") in payload:
                payload = str(payload).replace("live_token", bankOneToken)

            header = json.loads(header)
            payload = json.loads(payload)

            if verb == "GET":
                response = requests.request("GET", url, params=payload, headers=header)
            if verb == "POST":
                response = requests.request("POST", url, data=payload, headers=header)

            log_request(
                "CALLING BANKONE_API FROM MOBILE ||", f"URL: {url}", f"headers: {header}",
                f"payload: {payload}", f"response: {response.json()}, response_code: {response.status_code}"
            )
            request.graylog.info(
                "API Call was successful \n url: {url} \n headers: {headers} \n payload: {payload} \n "
                "response: {response}", url=url, payload=payload, headers=header, response=response.json()
            )
            return Response(response.json(), status=response.status_code)
        except Exception as err:
            log_request("An error has occurred", f"error: {err}")


class SignupView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            account_no = request.data.get('account_no')
            bank_id = request.data.get("bank_id")

            if not account_no:
                return Response({'detail': "Please enter account number"}, status=status.HTTP_400_BAD_REQUEST)

            data = request.data
            bank = Bank.objects.get(id=bank_id)

            if bank.active is False:
                return Response({'detail': "Error, bank is inactive"}, status=status.HTTP_400_BAD_REQUEST)

            if bank.short_name == "cit":
                success, detail = cit_create_new_customer(data, account_no)
                if not success:
                    log_request(f"error-message: {detail}")
                    return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'detail': detail})
        except Exception as ex:
            log_request(f"error-message: {ex}")
            return Response({'detail': "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        detail, success = authenticate_user(request)
        if success is True:
            try:
                customer = Customer.objects.get(user=request.user)
            except Exception as ex:
                log_request(f"error-message: {ex}")
                return Response({"detail": "An error occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)
            data = dict()
            if customer.bank.short_name == "cit":
                response = get_details_by_customer_id(customer.customerID).json()
                accounts = response["Accounts"]
                customer_account = list()
                for account in accounts:
                    if account["NUBAN"]:
                        account_detail = dict()
                        account_detail["account_no"] = account["NUBAN"]
                        account_detail["ledger_balance"] = account["ledgerBalance"]
                        account_detail["withdrawable_balance"] = account["withdrawableAmount"]
                        account_detail["kyc_level"] = account["kycLevel"]
                        account_detail["available_balance"] = account["availableBalance"]
                        customer_account.append(account_detail)
                data["account_balances"] = customer_account

            data["customer"] = CustomerSerializer(customer, context={"request": request}).data
            return Response({
                "detail": detail, "access_token": str(AccessToken.for_user(request.user)),
                "refresh_token": str(RefreshToken.for_user(request.user)), 'data': data})
        log_request(f"error-message: {detail}")
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class SignupOtpView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            account_no = request.data.get('account_no')
            bank_id = request.data.get('bank_id')

            if not account_no:
                log_request("detail: Account number is required")
                return Response({'detail': 'Account number is required'}, status=status.HTTP_400_BAD_REQUEST)

            if CustomerAccount.objects.filter(account_no=account_no).exists():
                log_request("detail: Account already registered")
                return Response({'detail': 'Account already registered'}, status=status.HTTP_400_BAD_REQUEST)

            bank = Bank.objects.get(id=bank_id)

            if bank.active is False:
                return Response({'detail': "Error, bank is inactive"}, status=status.HTTP_400_BAD_REQUEST)

            if bank.short_name == "cit":
                response = get_account_by_account_no(account_no)
                if response.status_code != 200:
                    for response in response.json():
                        detail = response['error-Message']
                        log_request(f"error-message: {detail}")
                        return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

                customer_data = response.json()
                phone_number = customer_data['CustomerDetails']['PhoneNumber']
                email = customer_data['CustomerDetails']['Email']
                name = str(customer_data['CustomerDetails']['Name']).split()[0]

                otp = generate_new_otp(phone_number)
                content = f"Dear {name}, \nKindly use this OTP: {otp} to complete " \
                          f"your registration on CIT Mobile App."
                subject = "CIT Mobile Registration"
                success, detail = send_otp_message(phone_number, content, subject, account_no, email)
                if success is False:
                    log_request(f"error-message: {detail}")
                    return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as err:
            return Response({'detail': "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class CustomerProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = CustomerSerializer(Customer.objects.get(user=request.user), context={'request': request}).data
        return Response(query)

    def put(self, request):
        profile_picture = request.data.get('profile_picture')

        if not profile_picture:
            log_request(f"error-message: No picture selected")
            return Response({'detail': 'No picture selected'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            customer = Customer.objects.get(user=request.user)
            customer.image = profile_picture
            customer.save()
            return Response({'detail': 'Profile updated'})
        except Exception as err:
            log_request(f"error-message: {err}")
            return Response({'detail': 'An error has occurred', 'error': str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):

    def post(self, request):
        try:
            old_password = request.data.get('old_password', '')
            new_password = request.data.get('new_password', '')
            confirm_password = request.data.get('confirm_password', '')

            # Check if old password matches the present password
            old_user_password = request.user.check_password(old_password)

            if not old_user_password:
                log_request("detail: Old password is wrong")
                return Response({"detail": "Old password is wrong"}, status=status.HTTP_400_BAD_REQUEST)

            if not (new_password.isnumeric() and len(new_password) == 6):
                log_request("detail: Password must be only 6 digits")
                return Response({"detail": "Password can only be 6 digit"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if old and new password are the same.
            if old_password == new_password:
                log_request("detail: previously used passwords not allowed")
                return Response({"detail": "previously used passwords are not allowed"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if new and confirm password are not the same
            if new_password != confirm_password:
                log_request("detail: passwords mismatch")
                return Response({"detail": "Passwords, does not match"}, status=status.HTTP_400_BAD_REQUEST)

            user = request.user
            user.set_password(new_password)
            user.save()

            return Response({"detail": "Password change successfully"})
        except (Exception,) as err:
            log_request(f"error-message: {err}")
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ResetOTPView(APIView):
    permission_classes = []

    def post(self, request):
        phone_number = request.data.get('phone_number')
        reset_type = request.data.get('reset_type', 'password')  # password or transaction pin
        if not phone_number:
            log_request("detail: phone number is required")
            return Response({"detail": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not Customer.objects.filter(phone_number=phone_number).exists():
            log_request("detail: customer does not exist")
            return Response({"detail": "Customer does not exist"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            customer = Customer.objects.get(phone_number=phone_number)
            customer_acct = CustomerAccount.objects.filter(customer=customer).first()
            # user_phone_number = customer.phone_number
            # if user_phone_number is not None:
            otp = generate_new_otp(phone_number)
            first_name = customer.user.first_name
            account_no = customer_acct.account_no
            content = f"Dear {first_name},\nKindly use this OTP: {otp} to reset your {reset_type} on CIT Mobile App."
            subject = f"Reset {reset_type} on CIT Mobile"
            email = customer.user.email
            success, detail = send_otp_message(phone_number, content, subject, account_no, email)
            if success is False:
                log_request(f"error-message: {detail}")
                return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'detail': detail})
        except (Exception,) as err:
            log_request(f"error-message: {err}")
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        otp = request.data.get('otp', '')
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')
        phone_number = request.data.get('phone_number', '')
        fields = [otp, new_password, confirm_password, phone_number]

        # Check if all fields are empty
        if not all(fields):
            return Response({"detail": "Requires OTP, New Password, Confirm Password and Phone number Fields"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            # user = User.objects.get(email=email)
            customer = Customer.objects.get(phone_number=phone_number)

            if otp != CustomerOTP.objects.get(phone_number=phone_number).otp:
                log_request(f"error-message: Invalid OTP")
                return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

            if not (new_password.isnumeric() and len(new_password) == 6):
                log_request(f"error-message: Password can only be 6 digit")
                return Response({"detail": "Password can only be 6 digit"}, status=status.HTTP_400_BAD_REQUEST)

            if new_password != confirm_password:
                log_request(f"error-message: Passwords does not match")
                return Response({"detail": "Passwords does not match"}, status=status.HTTP_400_BAD_REQUEST)

            user = customer.user

            user.set_password(new_password)
            user.save()
            # CustomerOTP.objects.filter(phone_number=phone_number).update(otp=str(uuid.uuid4().int)[:6])
            new_otp = CustomerOTP.objects.get(phone_number=phone_number)
            new_otp.otp = str(uuid.uuid4().int)[:6]
            new_otp.save()
            return Response({"detail": "Successfully changed Password, Login with your new password."})

        except (Exception,) as err:
            log_request(f"error-message: {err}")
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ChangeTransactionPinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            old_pin, new_pin, confirm_pin = data.get('old_pin', ''), data.get('new_pin', ''), data.get('confirm_pin',
                                                                                                       '')
            fields = [old_pin, new_pin, confirm_pin]

            if not all(fields):
                return Response({"detail": "Requires Old, New and Confirm Transaction PIN"},
                                status=status.HTTP_400_BAD_REQUEST)

            customer = Customer.objects.get(user=request.user)
            pin = decrypt_text(customer.transaction_pin)

            if old_pin != pin:
                log_request(f"error-message: Old PIN not correct")
                return Response({"detail": "Old PIN is not correct"}, status=status.HTTP_400_BAD_REQUEST)

            if not (new_pin.isnumeric() and len(new_pin) == 4):
                log_request(f"error-message: PIN must be 4 digits")
                return Response({"detail": "PIN must be 4 digits"}, status=status.HTTP_400_BAD_REQUEST)

            if new_pin != confirm_pin:
                log_request(f"error-message: PIN does not match")
                return Response({"detail": "PIN does not match"}, status=status.HTTP_400_BAD_REQUEST)

            if new_pin == old_pin:
                log_request(f"error-message: New Pin can't be the same as the Old Pin")
                return Response({"detail": "New Pin can't be the same as the Old Pin"},
                                status=status.HTTP_400_BAD_REQUEST)

            encrypt_new_pin = encrypt_text(new_pin)
            customer.transaction_pin = encrypt_new_pin
            customer.save()

            return Response({"detail": "Transaction PIN changed successfully"})
        except (Exception,) as err:
            log_request(f"error-message: {err}")
            return Response({"detail": "An error occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ResetTransactionPinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('otp')
        new_pin = request.data.get('new_pin')
        confirm_new_pin = request.data.get('confirm_new_pin')

        if not (token and new_pin and confirm_new_pin):
            log_request(f"error-message: You may have missed the PIN or OTP input")
            return Response({'detail': 'You may have missed the PIN or OTP input, please check'},
                            status=status.HTTP_400_BAD_REQUEST)

        customer = Customer.objects.get(user=request.user)
        otp = CustomerOTP.objects.get(phone_number=customer.phone_number).otp

        if token != otp:
            log_request(f"error-message: Invalid OTP")
            return Response({"detail": "OTP is not valid"}, status=status.HTTP_400_BAD_REQUEST)

        old_tran_pin = decrypt_text(customer.transaction_pin)

        if old_tran_pin == new_pin:
            log_request(f"error-message: Invalid PIN")
            return Response({"detail": "PIN not allowed"}, status=status.HTTP_400_BAD_REQUEST)

        if not (new_pin.isnumeric() and len(new_pin) == 4):
            log_request(f"error-message: PIN not 4 digits")
            return Response({"detail": "PIN must be 4 digits"}, status=status.HTTP_400_BAD_REQUEST)

        if new_pin != confirm_new_pin:
            log_request(f"error-message: PINs not matching")
            return Response({"detail": "PIN mismatch"}, status=status.HTTP_400_BAD_REQUEST)

        encrypt_new_pin = encrypt_text(new_pin)
        customer.transaction_pin = encrypt_new_pin
        customer.save()

        customer_token = CustomerOTP.objects.get(phone_number=customer.phone_number)
        customer_token.otp = str(uuid.uuid4().int)[:6]
        customer_token.save()

        return Response({"detail": "You have successfully reset your transaction PIN"})


class TransactionView(APIView, CustomPagination):

    def get(self, request, ref=None):
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")
        search = request.GET.get("search", "")

        if ref:
            try:
                data = TransactionSerializer(Transaction.objects.get(reference=ref)).data
                return Response(data)
            except Exception as err:
                log_request(f"error-message: {err}")
                return Response({"detail": str(err)})

        query = Q(customer__user=request.user)

        if search:
            query = query | Q(beneficiary_name__icontains=search)
            query = query | Q(beneficiary_number__icontains=search)

        if date_from or date_to:
            if not all([date_to, date_from]):
                log_request(f"error-message: date_from and date_to not selected")
                return Response({"detail": "date_from and date_to are required to filter"},
                                status=status.HTTP_400_BAD_REQUEST)
            query = query & Q(created_on__range=[date_from, date_to])

        queryset = Transaction.objects.filter(query).order_by('-id').distinct()
        transaction = self.paginate_queryset(queryset, request)
        data = self.get_paginated_response(TransactionSerializer(transaction, many=True).data).data
        return Response(data)

    def post(self, request):

        success, response = confirm_trans_pin(request)

        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        success, response = create_transaction(request)
        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Successfully created a transaction", "reference_code": str(response)})

    def put(self, request, ref):
        trans_status = request.data.get('status')
        if not trans_status:
            log_request(f"error-message: status is required")
            return Response({"detail": "status is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(reference=ref)
            transaction.status = trans_status
            transaction.save()
            return Response({"detail": "Successfully updated transaction"})
        except Exception as err:
            log_request(f"error-message: {err}")
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class BeneficiaryView(APIView, CustomPagination):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            beneficiary_type = request.GET.get("beneficiary_type")
            search = request.GET.get("search")

            if "search" in request.GET and "beneficiary_type" not in request.GET:
                log_request(f"error-message: beneficiary type not selected")
                return Response({"detail": "beneficiary type is required"}, status=status.HTTP_400_BAD_REQUEST)

            customer = Customer.objects.get(user=request.user)

            beneficiaries = Beneficiary.objects.filter(customer=customer)

            if beneficiary_type and search:
                query = Q(beneficiary_name__icontains=search)
                query |= Q(beneficiary_bank__icontains=search)
                query |= Q(beneficiary_acct_no__icontains=search)
                query |= Q(beneficiary_number__icontains=search)
                query |= Q(biller_name__icontains=search)
                beneficiaries = Beneficiary.objects.filter(query, customer=customer, beneficiary_type=beneficiary_type)

            if beneficiary_type and not search:
                beneficiaries = Beneficiary.objects.filter(customer=customer, beneficiary_type=beneficiary_type)

            paginate = self.paginate_queryset(beneficiaries, request)
            paginated_query = self.get_paginated_response(BeneficiarySerializer(paginate, many=True).data).data
            return Response({"detail": paginated_query})

        except KeyError as err:
            log_request(f"error-message: {err}")
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as err:
            log_request(f"error-message: {err}")
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        data = request.data
        try:
            beneficiary_name: str = data.get('beneficiary_name')
            beneficiary_bank: str = data.get('beneficiary_bank')
            beneficiary_type: str = data.get('beneficiary_type')
            beneficiary_acct_no: str = data.get('beneficiary_acct_no')
            beneficiary_number: str = data.get('beneficiary_number')
            biller_name: str = data.get('biller_name')

            if not beneficiary_type or beneficiary_type is None:
                log_request(f"error-message: beneficiary type is not selected")
                raise KeyError("Beneficiary type is required")

            if beneficiary_type == "cit_bank_transfer":
                if not all([beneficiary_name, beneficiary_acct_no]):
                    log_request(f"error-message: beneficiary name and account number is required")
                    raise KeyError("Beneficiary Name and Account Number are required fields for Type CIT BANK TRANSFER")

            if beneficiary_type == "other_bank_transfer":
                if not all([beneficiary_name, beneficiary_bank, beneficiary_acct_no]):
                    log_request(f"error-message: beneficiary name, bank, and account number is required")
                    raise KeyError("Beneficiary Name, Bank and Account Number are required for Type "
                                   "OTHER BANK TRANSFER")

            if beneficiary_type in ('airtime', 'data', 'utility'):
                if not all([beneficiary_number, biller_name]):
                    log_request(f"error-message: beneficiary number and biller name is required")
                    raise KeyError("Beneficiary Number and Biller's Name are required")

            customer = Customer.objects.get(user=request.user)
            beneficiary_instance, success = Beneficiary.objects.get_or_create(
                customer=customer,
                beneficiary_type=beneficiary_type,
                beneficiary_name=beneficiary_name,
                beneficiary_bank=beneficiary_bank,
                beneficiary_acct_no=beneficiary_acct_no,
                beneficiary_number=beneficiary_number,
                biller_name=biller_name
            )
            if not success:
                log_request(f"error-message: beneficiary already added")
                return Response({"detail": "Already a beneficiary"}, status=status.HTTP_302_FOUND)

        except KeyError as err:
            log_request(f"error-message: {err}")
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        except Customer.DoesNotExist as err:
            log_request(f"error-message: {err}")
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        except (Exception,) as err:
            log_request(f"error-message: {err}")
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Successfully created beneficiary"})


class ConfirmTransactionPin(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pin = request.data.get("pin", "")

        if not pin:
            log_request(f"error-message: PIN is required")
            return Response({"detail": "pin is a required field"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = Customer.objects.get(user=request.user)
            if user is None:
                log_request(f"error-message: User not found")
                return Response({"detail": "This user is not Found"}, status=status.HTTP_404_NOT_FOUND)

            if decrypt_text(user.transaction_pin) != pin:
                log_request(f"error-message: Incorrect transaction pin")
                return Response({"detail": "Transaction Pin Does Not Match"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as err:
            log_request(f"error-message: {err}")
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Transaction Pin is Correct"})


class FeedbackView(APIView):

    def post(self, request):
        message = request.data.get("message")
        message_type = request.data.get("message_type")

        name = str("{} {}").format(self.request.user.first_name, self.request.user.last_name).capitalize()

        if not all([message, message_type]):
            log_request(f"error-message: required are message and message_type")
            return Response({"detail": "message and message_type are required"}, status=status.HTTP_400_BAD_REQUEST)

        rating_email = settings.CIT_ACCOUNT_OFFICE_RATING_EMAIL
        feedback_email = settings.CIT_FEEDBACK_EMAIL
        enquiry_email = settings.CIT_ENQUIRY_EMAIL

        if message_type == "account_manager_rating":
            subject, receiver = f"ACCOUNT OFFICER RATING FROM {name}", rating_email
        elif message_type == "feedback_email":
            subject, receiver = f"FEEDBACK FROM {name}", feedback_email
        else:
            subject, receiver = f"ENQUIRY FROM {name}", enquiry_email

        Thread(target=send_email, args=[request.user.email, receiver, subject, message])

        return Response({"detail": "Message sent successfully"})


class GenerateRandomCode(APIView):
    permission_classes = []

    def get(self, request):
        code = generate_random_ref_code()
        return Response({"detail": code})


class BankAPIView(generics.ListAPIView):
    permission_classes = []
    serializer_class = BankSerializer
    queryset = Bank.objects.all()



