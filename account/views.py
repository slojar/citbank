import datetime
import decimal
import json
import uuid
import requests
from threading import Thread

from django.db.models import Q, Sum
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from billpayment.models import Airtime, Data, CableTV, Electricity
from .paginations import CustomPagination
from .serializers import CustomerSerializer, TransferSerializer, BeneficiarySerializer, BankSerializer
from .utils import authenticate_user, generate_new_otp, \
    decrypt_text, encrypt_text, confirm_trans_pin, open_account_with_banks, get_account_balance, \
    get_previous_date, get_month_start_and_end_datetime, get_week_start_and_end_datetime, \
    get_year_start_and_end_datetime, get_transaction_history, generate_bank_statement, log_request, get_account_officer, \
    get_bank_flex_balance, perform_bank_transfer, perform_name_query, retrieve_customer_card, block_or_unblock_card, \
    perform_bvn_validation, get_fix_deposit_accounts, create_or_update_bank

from bankone.api import bankone_get_account_by_account_no, bankone_send_otp_message, bankone_create_new_customer, \
    generate_random_ref_code, bankone_send_email, bankone_send_statement
from .models import CustomerAccount, Customer, CustomerOTP, Transaction, Beneficiary, Bank

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


class HomepageView(APIView):
    permission_classes = []

    def get(self, request):
        return HttpResponse("<h1>Welcome to BankPro</h1>")


class RerouteView(APIView):
    permission_classes = []

    def post(self, request):
        return Response({"detail": "A new version of the app is available on the store, please download"}, status=status.HTTP_400_BAD_REQUEST)
        # try:
        #     url = request.data.get("url", "")
        #     verb = request.data.get("method", "GET")
        #     header = request.data.get("header", {})
        #     payload = request.data.get("payload", {})
        #
        #     header = json.dumps(header)
        #     payload = json.dumps(payload)
        #
        #     response = {}
        #
        #     if str("live_token") in url:
        #         url = str(url).replace("live_token", bankOneToken)
        #     if str("live_token") in header:
        #         header = str(header).replace("live_token", bankOneToken)
        #     if str("live_token") in payload:
        #         payload = str(payload).replace("live_token", bankOneToken)
        #
        #     header = json.loads(header)
        #     payload = json.loads(payload)
        #
        #     if verb == "GET":
        #         response = requests.request("GET", url, params=payload, headers=header)
        #     if verb == "POST":
        #         response = requests.request("POST", url, data=payload, headers=header)
        #
        #     log_request(
        #         "CALLING BANKONE_API FROM MOBILE ||", f"URL: {url}", f"headers: {header}",
        #         f"payload: {payload}", f"response: {response.json()}, response_code: {response.status_code}"
        #     )
        #     request.graylog.info(
        #         "API Call was successful \n url: {url} \n headers: {headers} \n payload: {payload} \n "
        #         "response: {response}", url=url, payload=payload, headers=header, response=response.json()
        #     )
        #     return Response(response.json(), status=response.status_code)
        # except Exception as err:
        #     log_request("An error has occurred", f"error: {err}")
        #     return Response({"detail": "An error has occurred, please try again later"})


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

            if bank.short_name in bank_one_banks:
                success, detail = bankone_create_new_customer(data, account_no, bank)
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
        version = request.data.get("build")

        detail, success = authenticate_user(request)
        if success is True:
            try:
                customer = Customer.objects.get(user=request.user)
                if not version or version < customer.bank.app_version:
                    return Response({"detail": "Please download the latest version from your store"},
                                    status=status.HTTP_400_BAD_REQUEST)
            except Exception as ex:
                log_request(f"error-message: {ex}")
                return Response({"detail": "An error occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)
            data = get_account_balance(customer, request)
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
            phone_number = content = subject = email = None
            bank_one_banks = json.loads(settings.BANK_ONE_BANKS)
            short_name = bank.short_name
            decrypted_token = decrypt_text(bank.auth_token)

            if bank.active is False:
                return Response({'detail': "Error, bank is inactive"}, status=status.HTTP_400_BAD_REQUEST)

            # GET CUSTOMER PHONE NUMBER AND EMAIL
            if short_name in bank_one_banks:
                response = bankone_get_account_by_account_no(account_no, decrypted_token)
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
                sh_name = str(bank.name).upper()
                content = f"Dear {name}, \nKindly use this OTP: {otp} to complete " \
                          f"your registration on {sh_name}."
                subject = f"{sh_name} Registration"
            # SEND OTP TO USER
            success, detail = bankone_send_otp_message(phone_number, content, subject, account_no, email, bank)
            if success is False:
                log_request(f"error-message: {detail}")
                return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "OPT sent to email and phone number"})
        except Exception as err:
            log_request(f"error-message: {err}")
            return Response({'detail': "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class CustomerProfileView(APIView):

    def get(self, request):
        customer = Customer.objects.get(user=request.user)
        data = get_account_balance(customer, request)
        return Response(data)

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

            # Remove white spaces
            old_password = str(old_password).replace(" ", "")
            new_password = str(new_password).replace(" ", "")
            confirm_password = str(confirm_password).replace(" ", "")

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
                return Response({"detail": "previously used passwords are not allowed"},
                                status=status.HTTP_400_BAD_REQUEST)

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
            bank = customer.bank
            # user_phone_number = customer.phone_number
            # if user_phone_number is not None:
            otp = generate_new_otp(phone_number)
            first_name = customer.user.first_name
            account_no = customer_acct.account_no
            email = customer.user.email
            content = subject = ""
            if bank.short_name in bank_one_banks:
                s_name = str(bank.name).upper()
                content = f"Dear {first_name},\nKindly use this OTP: {otp} to reset your {reset_type} on {s_name}."
                subject = f"Reset {reset_type} on {s_name}"
            success, detail = bankone_send_otp_message(phone_number, content, subject, account_no, email, bank)
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

        # Remove white spaces
        new_password = str(new_password).replace(" ", "")
        confirm_password = str(confirm_password).replace(" ", "")

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
            CustomerOTP.objects.filter(phone_number=phone_number).update(otp=str(uuid.uuid4().int)[:6])
            # new_otp = CustomerOTP.objects.get(phone_number=phone_number)
            # new_otp.otp = str(uuid.uuid4().int)[:6]
            # new_otp.save()
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
                data = TransferSerializer(Transaction.objects.get(reference=ref)).data
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
        data = self.get_paginated_response(TransferSerializer(transaction, many=True).data).data
        return Response(data)


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

            # To be removed when Mobile APP update beneficiary type
            query = Q(customer=customer)
            if beneficiary_type == "local_transfer" or beneficiary_type == "cit_bank_transfer":
                query &= Q(beneficiary_type="local_transfer") | Q(beneficiary_type="cit_bank_transfer")

            if beneficiary_type == "external_transfer" or beneficiary_type == "other_bank_transfer":
                query &= Q(beneficiary_type="external_transfer") | Q(beneficiary_type="other_bank_transfer")

            if beneficiary_type == "airtime":
                query &= Q(beneficiary_type="airtime")

            if beneficiary_type == "data":
                query &= Q(beneficiary_type="data")

            if beneficiary_type == "utility":
                query &= Q(beneficiary_type="utility")

            if search:
                query &= Q(beneficiary_name__icontains=search) | Q(beneficiary_bank__icontains=search) | \
                         Q(beneficiary_acct_no__icontains=search) | Q(beneficiary_number__icontains=search) | \
                         Q(biller_name__icontains=search)

            beneficiaries = Beneficiary.objects.filter(query)

            # if beneficiary_type and search:
            #     query = Q(beneficiary_name__icontains=search)
            #     query |= Q(beneficiary_bank__icontains=search)
            #     query |= Q(beneficiary_acct_no__icontains=search)
            #     query |= Q(beneficiary_number__icontains=search)
            #     query |= Q(biller_name__icontains=search)
            #     beneficiaries = Beneficiary.objects.filter(query, customer=customer, beneficiary_type=beneficiary_type)
            #
            # if beneficiary_type and not search:
            #     beneficiaries = Beneficiary.objects.filter(customer=customer, beneficiary_type=beneficiary_type)

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

            if beneficiary_type == "local_transfer":
                if not all([beneficiary_name, beneficiary_acct_no]):
                    log_request(f"error-message: beneficiary name and account number is required")
                    raise KeyError("Beneficiary Name and Account Number are required fields for Type SAME BANK TRANSFER")

            if beneficiary_type == "external_transfer":
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
        customer = get_object_or_404(Customer, user=request.user)

        if not all([message, message_type]):
            log_request(f"error-message: required are message and message_type")
            return Response({"detail": "message and message_type are required"}, status=status.HTTP_400_BAD_REQUEST)

        rating_email = customer.bank.officer_rating_email
        feedback_email = customer.bank.feedback_email
        enquiry_email = customer.bank.enquiry_email
        institution_code = decrypt_text(customer.bank.institution_code)
        mfb_code = decrypt_text(customer.bank.mfb_code)

        if message_type == "account_manager_rating":
            subject, receiver = f"ACCOUNT OFFICER RATING FROM {name}", rating_email
        elif message_type == "feedback_email":
            subject, receiver = f"FEEDBACK FROM {name}", feedback_email
        else:
            subject, receiver = f"ENQUIRY FROM {name}", enquiry_email

        Thread(target=bankone_send_email, args=[request.user.email, receiver, subject, message, institution_code, mfb_code])

        return Response({"detail": "Message sent successfully"})


# class GenerateRandomCode(APIView):
#     permission_classes = []
#
#     def get(self, request):
#         code = generate_random_ref_code()
#         return Response({"detail": code})


class OldBankAPIListView(generics.ListAPIView):
    permission_classes = []
    serializer_class = BankSerializer
    queryset = Bank.objects.all()


class BankAPIListView(APIView):
    permission_classes = []

    def post(self, request):
        name = request.data.get("name")

        if not name:
            return Response({"detail": "Bank name is required"}, status=status.HTTP_400_BAD_REQUEST)

        bank, create = Bank.objects.get_or_create(name=name)
        create_or_update_bank(request, bank)
        return Response(BankSerializer(bank, context={"request": request}).data)

    def get(self, request):
        return Response(BankSerializer(Bank.objects.all(), many=True).data)


class OpenAccountAPIView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            bank_id = request.data.get("bank_id")
            if not bank_id:
                return Response({"detail": "bank_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            bank = Bank.objects.get(id=bank_id)

            success, detail = open_account_with_banks(bank, request)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": detail})
        except Exception as err:
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class CustomerDashboardAPIView(APIView):

    def get(self, request, bank_id):

        # try:
        account_no = [
            account.account_no for account in
            CustomerAccount.objects.filter(customer__user=request.user, customer__bank_id=bank_id)
        ]

        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        last_7_days = request.GET.get("last_7_days")
        this_month = request.GET.get("this_month")
        this_year = request.GET.get("this_year")
        this_week = request.GET.get("this_week")

        present_day = datetime.datetime.now()
        if last_7_days == "true":
            past_7_day = get_previous_date(date=present_day, delta=7)
            start_date = past_7_day
            end_date = present_day
        elif this_month == "true":
            month_start, month_end = get_month_start_and_end_datetime(present_day)
            start_date = month_start
            end_date = month_end
        elif this_year == "true":
            year_start, year_end = get_year_start_and_end_datetime(present_day)
            start_date = year_start
            end_date = year_end
        elif this_week == "true":
            week_start, week_end = get_week_start_and_end_datetime(present_day)
            start_date = week_start
            end_date = week_end
        else:
            start_date = date_from
            end_date = date_to

        transfer = Transaction.objects.filter(created_on__range=(start_date, end_date), customer__user=request.user)
        airtime = Airtime.objects.filter(
            created_on__range=(start_date, end_date), account_no__in=account_no, status__iexact="success"
        ).distinct()
        data = Data.objects.filter(
            created_on__range=(start_date, end_date), account_no__in=account_no, status__iexact="success"
        ).distinct()
        cable = CableTV.objects.filter(
            created_on__range=(start_date, end_date), account_no__in=account_no, status__iexact="success"
        ).distinct()
        electricity = Electricity.objects.filter(
            created_on__range=(start_date, end_date), account_no__in=account_no, status__iexact="success"
        ).distinct()

        account_number = CustomerAccount.objects.filter(customer__user=request.user).first().account_no

        bank = Bank.objects.get(id=bank_id)
        last_ten_trans, pagination = get_transaction_history(bank, account_number)

        result = dict()
        result["transfer"] = dict()
        result["transfer"]["total"] = transfer.count()
        result["transfer"]["amount"] = transfer.aggregate(Sum("amount"))["amount__sum"] or 0

        result["airtime"] = dict()
        result["airtime"]["total"] = airtime.count()
        result["airtime"]["amount"] = airtime.aggregate(Sum("amount"))["amount__sum"] or 0

        result["data"] = dict()
        result["data"]["total"] = data.count()
        result["data"]["amount"] = data.aggregate(Sum("amount"))["amount__sum"] or 0

        result["cableTv"] = dict()
        result["cableTv"]["total"] = cable.count()
        result["cableTv"]["amount"] = cable.aggregate(Sum("amount"))["amount__sum"] or 0

        result["electricity"] = dict()
        result["electricity"]["total"] = electricity.count()
        result["electricity"]["amount"] = electricity.aggregate(Sum("amount"))["amount__sum"] or 0

        result["recent_transactions"] = last_ten_trans

        return Response(result)
        # except Exception as ex:
        #     return Response({"detail": "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class BankHistoryAPIView(APIView):

    def get(self, request, bank_id):

        try:
            account_no = request.GET.get("account_no")
            date_from = request.GET.get("date_from")
            date_to = request.GET.get("date_to")
            page_no = request.GET.get("page_no")

            if not CustomerAccount.objects.filter(customer__user=request.user, account_no=account_no,
                                                  customer__bank_id=bank_id).exists():
                return Response({"detail": "Account number is not valid"}, status=status.HTTP_400_BAD_REQUEST)

            bank = Bank.objects.get(id=bank_id)
            result, pages = get_transaction_history(bank, account_no, date_from, date_to, page_no)

            return Response({"detail": result, "pagination": pages})

        except Exception as err:
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class GenerateStatement(APIView):

    def post(self, request, bank_id):
        try:
            date_from = request.data.get("date_from")
            date_to = request.data.get("date_to")
            account_no = request.data.get("account_no")
            download = request.data.get("download")
            email = request.data.get("email")

            if not all([date_to, date_from, account_no]):
                return Response({"detail": "Dates and account number are required"}, status=status.HTTP_400_BAD_REQUEST)

            if not CustomerAccount.objects.filter(
                    customer__user=request.user, customer__bank_id=bank_id, account_no=account_no).exists():
                return Response({"detail": "Account not valid for user"}, status=status.HTTP_400_BAD_REQUEST)

            bank = Bank.objects.get(id=bank_id)
            if download is True:
                success, response = generate_bank_statement(request, bank, date_from, date_to, account_no, "pdf")
            else:
                success, response = generate_bank_statement(request, bank, date_from, date_to, account_no, "pdf")
                if success is True:
                    if email:
                        # Send statement to customer
                        response = bankone_send_statement(request, bank, response)

            if success is False:
                return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": response})
        except Exception as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class AccountOfficerAPIView(APIView):

    def get(self, request):
        account_no = request.GET.get("account_no")

        if not CustomerAccount.objects.filter(account_no=account_no).exists():
            return Response({"detail": "User with account not found"}, status=status.HTTP_400_BAD_REQUEST)

        account = CustomerAccount.objects.get(account_no=account_no)

        data = get_account_officer(account)

        return Response({"detail": data})


class BankFlexAPIView(APIView):

    def get(self, request, bank_id):

        try:
            customer = Customer.objects.get(user=request.user, bank_id=bank_id)

            success, detail = get_bank_flex_balance(customer)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": detail})
        except Exception as err:
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class TransferAPIView(APIView):

    def post(self, request, bank_id):
        try:
            bank = get_object_or_404(Bank, id=bank_id)
            success, detail = perform_bank_transfer(bank, request)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            data = TransferSerializer(detail).data
            return Response({"detail": "Transfer successful", "data": data})
        except Exception as ex:
            return Response({"detail": "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class NameEnquiryAPIView(APIView):

    def get(self, request, bank_id):

        try:
            bank = Bank.objects.get(id=bank_id)
            success, detail = perform_name_query(bank, request)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response(detail)
        except Exception as err:
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class CardOperationAPIView(APIView):

    def get(self, request):
        account_no = request.GET.get("account_no")

        try:
            customer = Customer.objects.get(user=request.user)
            success, detail = retrieve_customer_card(customer, account_no)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": detail})
        except Exception as ex:
            return Response({"detail": "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        try:
            success, detail = block_or_unblock_card(request)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": detail})
        except Exception as err:
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ValidateBVNAPIView(APIView):
    permission_classes = []

    def post(self, request, bank_id):
        bvn = request.data.get("bvn")

        if not bvn:
            return Response({"detail": "BVN is required"}, status=status.HTTP_400_BAD_REQUEST)

        bank = get_object_or_404(Bank, id=bank_id)

        success, response = perform_bvn_validation(bank, bvn)
        if success is False:
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": response})


class FixDepositAPIView(APIView):

    def get(self, request, bank_id):
        bank = get_object_or_404(Bank, id=bank_id)
        success, response = get_fix_deposit_accounts(bank, request)
        if success is False:
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)
        return Response(response)

