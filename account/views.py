import rest_framework.generics
from django.contrib.auth import login, authenticate, logout
from django.http import HttpResponse
from django.shortcuts import render
import re

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .serializers import CustomerSerializer
from .utils import create_new_customer, authenticate_user, validate_password

from bankone.api import get_account_by_account_no
from .models import CustomerAccount, Customer
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
    permission_classes = []

    def post(self, request):
        details, success = authenticate_user(request)
        data = CustomerSerializer(Customer.objects.get(user=request.user)).data
        if success:
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
        success, detail = send_otp_message(phone_number, content, account_no)
        if success is False:
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': detail})


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
                return Response({"detail": "password is wrong"})

            # Check if old and new password are the same.
            if old_password == new_password:
                return Response({"detail": "Old and New Password can't be the same"})

            # Check if new and confirm password are not the same
            if new_password != confirm_password:
                return Response({"detail": "New and Confirm Passwords, does not match"})

            # Check if password has atleast (more than 8 chars, 1 special char, 1 digit, 1 lower case, 1 Upper case)
            check, detail = validate_password(new_password)

            if not check:
                raise Exception(detail)

            user = request.user
            user.set_password(new_password)
            user.save()

            return Response({"detail": detail}, status=status.HTTP_201_CREATED)
        except (Exception, ) as err:
            return Response({"detail": str(err)}, status=status.HTTP_400_BAD_REQUEST)

