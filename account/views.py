import uuid
from threading import Thread

from django.db.models import Q
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .paginations import CustomPagination
from .serializers import CustomerSerializer, TransactionSerializer, BeneficiarySerializer
from .utils import create_new_customer, authenticate_user, validate_password, generate_new_otp, \
    send_otp_message, decrypt_text, encrypt_text, create_transaction

from bankone.api import get_account_by_account_no, send_enquiry_email
from .models import CustomerAccount, Customer, CustomerOTP, Transaction, Beneficiary


class SignupView(APIView):
    permission_classes = []

    def post(self, request):
        account_no = request.data.get('account_no')

        if not account_no:
            return Response({'detail': 'Please enter account number'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data

        success, detail = create_new_customer(data, account_no)
        if not success:
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': detail})


class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        details, success = authenticate_user(request)
        if success is True:
            data = CustomerSerializer(Customer.objects.get(user=request.user)).data
            return Response({
                "detail": details, "access_token": str(AccessToken.for_user(request.user)),
                "refresh_token": str(RefreshToken.for_user(request.user)), 'data': data})
        return Response({"detail": details}, status=status.HTTP_400_BAD_REQUEST)


class SignupOtpView(APIView):
    permission_classes = []

    def post(self, request):
        account_no = request.data.get('account_no')

        if not account_no:
            return Response({'detail': 'Account number is required'}, status=status.HTTP_400_BAD_REQUEST)

        if CustomerAccount.objects.filter(account_no=account_no).exists():
            return Response({'detail': 'Account already registered'}, status=status.HTTP_400_BAD_REQUEST)

        response = get_account_by_account_no(account_no)
        if response.status_code != 200:
            for response in response.json():
                detail = response['error-Message']
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
        # if success is False:
        #     return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        # return Response({'detail': detail})
        return Response({'detail': "OTP successfully sent", "otp": otp})  # To be removed when message API start working


class CustomerProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = CustomerSerializer(Customer.objects.get(user=request.user), context={'request': request}).data
        return Response(query)

    def put(self, request):
        profile_picture = request.data.get('profile_picture')

        if not profile_picture:
            return Response({'detail': 'No picture selected'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            customer = Customer.objects.get(user=request.user)
            customer.image = profile_picture
            customer.save()
            return Response({'detail': 'Profile updated'})
        except Exception as err:
            return Response({'detail': 'An error has occurred', 'error': str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):

    def post(self, request):
        try:
            data = request.data
            old_password = data.get('old_password', '')
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')
            # print(data, old_password, new_password)

            # Check if old password matches the present password
            old_user_password = request.user.check_password(old_password)

            if not old_user_password:
                return Response({"detail": "Old password is wrong"})

            # Check if old and new password are the same.
            if old_password == new_password:
                return Response({"detail": "previously used passwords are not allowed"})

            # Check if new and confirm password are not the same
            if new_password != confirm_password:
                return Response({"detail": "Passwords, does not match"})

            # Check if password has atleast (more than 8 chars, 1 special char, 1 digit, 1 lower case, 1 Upper case)
            check, detail = validate_password(new_password)

            if not check:
                raise Exception(detail)

            user = request.user
            user.set_password(new_password)
            user.save()

            return Response({"detail": detail})
        except (Exception,) as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ResetOTPView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        reset_type = request.data.get('reset_type', 'password')  # password or transaction pin
        if not email:
            return Response({"detail": "Email is required"})

        try:
            user = User.objects.get(email=email)
            customer = Customer.objects.get(user=user)
            customer_acct = CustomerAccount.objects.filter(customer=customer).first()
            user_phone_number = customer.phone_number
            if user_phone_number is not None:
                otp = generate_new_otp(user_phone_number)
                first_name = user.first_name
                account_no = customer_acct.account_no
                content = f"Dear {first_name},\nKindly use this OTP: {otp} to reset your {reset_type} on CIT Mobile App."
                subject = f"Reset {reset_type} on CIT Mobile"
                success, detail = send_otp_message(user_phone_number, content, subject, account_no, email)
                # if success is False:
                #     return Response({'detail': detail, "otp": otp}, status=status.HTTP_400_BAD_REQUEST)
                # return Response({'detail': detail})
                return Response(
                    {'detail': "OTP successfully sent", "otp": otp})  # To be removed when message API start working
        except (Exception,) as err:
            return Response({"detail": "Error", "data": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        otp = request.data.get('otp', '')
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')
        email = request.data.get('email', '')
        fields = [otp, new_password, confirm_password, email]

        # Check if all fields are empty
        if not all(fields):
            return Response({"detail": "Requires OTP, New Password, Confirm Password and Email Fields"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            phone_number = Customer.objects.get(user=user).phone_number

            if otp != CustomerOTP.objects.get(phone_number=phone_number).otp:
                return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

            if new_password != confirm_password:
                return Response({"detail": "Passwords does not match"}, status=status.HTTP_400_BAD_REQUEST)

            check, detail = validate_password(new_password)

            if not check:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

            if user is not None:
                user.set_password(new_password)
                user.save()
                # CustomerOTP.objects.get(phone_number=phone_number).update(otp=str(uuid.uuid4().int)[:6])
                new_otp = CustomerOTP.objects.get(phone_number=phone_number)
                new_otp.otp = str(uuid.uuid4().int)[:6]
                new_otp.save()
            return Response({"detail": "Successfully changed Password, Login with your new password."})

        except (Exception,) as err:
            return Response({"detail": "An Error Occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


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
                return Response({"detail": "Old PIN is not correct"}, status=status.HTTP_400_BAD_REQUEST)

            if not (new_pin.isnumeric() and len(new_pin) == 4):
                return Response({"detail": "PIN must be 4 digits"}, status=status.HTTP_400_BAD_REQUEST)

            if new_pin != confirm_pin:
                return Response({"detail": "PIN does not match"}, status=status.HTTP_400_BAD_REQUEST)

            if new_pin == old_pin:
                return Response({"detail": "New Pin can't be the same as the Old Pin"},
                                status=status.HTTP_400_BAD_REQUEST)

            encrypt_new_pin = encrypt_text(new_pin)
            customer.transaction_pin = encrypt_new_pin
            customer.save()

            return Response({"detail": "Transaction PIN changed successfully"})
        except (Exception,) as err:
            return Response({"detail": "An error occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ResetTransactionPinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('otp')
        new_pin = request.data.get('new_pin')
        confirm_new_pin = request.data.get('confirm_new_pin')

        if not (token and new_pin and confirm_new_pin):
            return Response({'detail': 'You may have missed the PIN or OTP input, please check'},
                            status=status.HTTP_400_BAD_REQUEST)

        customer = Customer.objects.get(user=request.user)
        otp = CustomerOTP.objects.get(phone_number=customer.phone_number).otp

        if token != otp:
            return Response({"detail": "OTP is not valid"}, status=status.HTTP_400_BAD_REQUEST)

        old_tran_pin = decrypt_text(customer.transaction_pin)

        if old_tran_pin == new_pin:
            return Response({"detail": "PIN not allowed"}, status=status.HTTP_400_BAD_REQUEST)

        if not (new_pin.isnumeric() and len(new_pin) == 4):
            return Response({"detail": "PIN must be 4 digits"}, status=status.HTTP_400_BAD_REQUEST)

        if new_pin != confirm_new_pin:
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
                return Response({"detail": str(err)})

        query = Q(customer__user=request.user)

        if search:
            query = query | Q(beneficiary_name__icontains=search)
            query = query | Q(beneficiary_number__icontains=search)

        if date_from or date_to:
            if not all([date_to, date_from]):
                return Response({"detail": "date_from and date_to are required to filter"},
                                status=status.HTTP_400_BAD_REQUEST)
            query = query & Q(created_on__range=[date_from, date_to])

        queryset = Transaction.objects.filter(query).order_by('-id').distinct()
        transaction = self.paginate_queryset(queryset, request)
        data = self.get_paginated_response(TransactionSerializer(transaction, many=True).data).data
        return Response(data)

    def post(self, request):
        trans_pin = request.data.get('transaction_pin')

        if not trans_pin:
            return Response({"detail": "Please enter your Transaction PIN"}, status=status.HTTP_400_BAD_REQUEST)

        customer_pin = Customer.objects.get(user=request.user).transaction_pin
        decrypted_pin = decrypt_text(customer_pin)

        if trans_pin != decrypted_pin:
            return Response({"detail": "Invalid Transaction PIN"}, status=status.HTTP_400_BAD_REQUEST)

        success, response = create_transaction(request)
        if success is False:
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Successfully created a transaction", "reference_code": str(response)})

    def put(self, request, ref):
        trans_status = request.data.get('status')
        if not trans_status:
            return Response({"detail": "status is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(reference=ref)
            transaction.status = trans_status
            transaction.save()
            return Response({"detail": "Successfully updated transaction"})
        except Exception as err:
            return Response({"detail": "An error has occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class BeneficiaryView(APIView, CustomPagination):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            beneficiary_type = request.GET.get("beneficiary_type")
            search = request.GET.get("search")

            if "search" in request.GET and "beneficiary_type" not in request.GET:
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
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as err:
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
                raise KeyError("Beneficiary type is required")

            if beneficiary_type == "cit_bank_transfer":
                if not all([beneficiary_name, beneficiary_acct_no]):
                    raise KeyError("Beneficiary Name and Account Number are required fields for Type CIT BANK TRANSFER")

            if beneficiary_type == "other_bank_transfer":
                if not all([beneficiary_name, beneficiary_bank, beneficiary_acct_no]):
                    raise KeyError("Beneficiary Name, Bank and Account Number are required for Type "
                                   "OTHER BANK TRANSFER")

            if beneficiary_type in ('airtime', 'data', 'utility'):
                if not all([beneficiary_number, biller_name]):
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
                return Response({"detail": "Already a beneficiary"}, status=status.HTTP_302_FOUND)

        except KeyError as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        except Customer.DoesNotExist as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        except (Exception,) as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Successfully created beneficiary"})


class ConfirmTransactionPin(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pin = request.data.get("pin", "")

        if not pin:
            return Response({"detail": "pin is a required field"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = Customer.objects.get(user=request.user)
            if user is None:
                return Response({"detail": "This user is not Found"}, status=status.HTTP_404_NOT_FOUND)

            if decrypt_text(user.transaction_pin) != pin:
                return Response({"detail": "Transaction Pin Does Not Match"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Transaction Pin is Correct"})


class FeedbackView(APIView):

    def post(self, request):
        message = request.data.get("message")
        message_type = request.data.get("message_type")

        name = str("{} {}").format(self.request.user.first_name, self.request.user.last_name).capitalize()

        if not all([message, message_type]):
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

        Thread(target=send_enquiry_email, args=[request.user.email, receiver, subject, message])

        return Response({"detail": "Message sent successfully"}, status=status.HTTP_400_BAD_REQUEST)


class GenerateRandomCode(APIView):
    permission_classes = []

    def get(self, request):
        from .utils import generate_random_ref_code
        code = generate_random_ref_code()
        return Response({"detail": code})







