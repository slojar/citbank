import rest_framework.generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from bankone.api import get_account_by_account_no
from .models import CustomerAccount
from .utils import create_new_customer, generate_new_otp, send_otp_message


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

    def post(self, request):

        return Response({})


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
        success, detail = send_otp_message(phone_number, content, account_no)
        if success is False:
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': detail})



