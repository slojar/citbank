from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .serializers import CustomerSerializer
from .utils import create_new_customer, authenticate_user

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



