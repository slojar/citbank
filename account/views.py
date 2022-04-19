from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .serializers import CustomerSerializer
from .utils import create_new_customer, authenticate_user, validate_password, generate_new_otp,\
    send_otp_message, decrypt_text, encrypt_text

from bankone.api import get_account_by_account_no
from .models import CustomerAccount, Customer, CustomerOTP


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
            return Response({'detail': 'Account number is required'})

        response = get_account_by_account_no(account_no)
        if response.status_code != 200:
            for response in response.json():
                detail = response['error-Message']
                return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        customer_data = response.json()
        phone_number = customer_data['CustomerDetails']['PhoneNumber']
        name = str(customer_data['CustomerDetails']['Name']).split()[0]

        otp = generate_new_otp(phone_number)
        content = f"Dear {name} \nKindly use this OTP: {otp} to complete " \
                  f"your registration on CIT Mobile App."
        # success, detail = send_otp_message(phone_number, content, account_no)
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
            return Response({'detail': 'No picture not selected'}, status=status.HTTP_400_BAD_REQUEST)
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


class ForgotPasswordOTPView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"detail": "Email is required"})

        try:
            user = User.objects.get(email=email)
            user_phone_number = Customer.objects.get(user=user).phone_number
            if user_phone_number is not None:
                otp = generate_new_otp(user_phone_number)

                # send otp via mail and sms

                return Response({"detail": "OTP successfully sent"}, status.HTTP_201_CREATED)
        except (Exception,) as err:
            return Response({"detail": "Error", "data": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPassword(APIView):
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
            otp = CustomerOTP.objects.get(otp=otp)
            user = User.objects.get(email=email)

            if new_password != confirm_password:
                return Response({"detail": "Passwords does not match"}, status=status.HTTP_400_BAD_REQUEST)

            check, detail = validate_password(new_password)

            if not check:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

            if user is not None:
                user.set_password(new_password)
                user.save()
            return Response({"detail": "Successfully changed Password , Login with your new password."})

        except (Exception, ) as err:
            return Response({"detail": "An Error Occured", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)


class ChangeTransactionPin(APIView):
    permission_classes = [IsAuthenticated]
    """
        Params:  old-pin, new-pin, confirm-pin
    """

    def post(self, request):
        try:
            data = request.data
            old_pin, new_pin, confirm_pin = data.get('old_pin', ''), data.get('new_pin', ''), data.get('confirm_pin', '')
            fields = [old_pin, new_pin, confirm_pin]

            if not all(fields):
                return Response({"detail": "Requires Old, New and Confirm Transaction Pins"},
                                status=status.HTTP_400_BAD_REQUEST)

            customer = Customer.objects.get(user=request.user)
            pin = decrypt_text(customer.transaction_pin)

            if old_pin != pin:
                return Response({"detail": "Old pin does not match current pin"}, status=status.HTTP_400_BAD_REQUEST)

            if not new_pin.isnumeric() or len(new_pin) != 4:
                return Response({"detail": "Pin must be 4 digits"}, status=status.HTTP_400_BAD_REQUEST)

            if new_pin != confirm_pin:
                return Response({"detail": "Pin does not match"}, status=status.HTTP_400_BAD_REQUEST)

            if new_pin == old_pin:
                return Response({"detail": "New Pin can't be the same as the Old Pin"}, status=status.HTTP_400_BAD_REQUEST)

            encrypt_new_pin = encrypt_text(new_pin)
            customer.transaction_pin = encrypt_new_pin
            customer.save()

            return Response({"detail": "Successfully Changed your Transaction Pin"})
        except (Exception, ) as err:
            return Response({"detail": "An error occurred", "error": str(err)}, status=status.HTTP_400_BAD_REQUEST)
