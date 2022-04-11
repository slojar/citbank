import rest_framework.generics
from django.contrib.auth import login, authenticate, logout
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from .utils import create_new_customer, authenticate_user


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
        if success:
            return Response({
                "detail": details, "success": success, "access_token": str(AccessToken.for_user(request.user)),
                "refresh_token": str(RefreshToken.for_user(request.user)), "status": status.HTTP_200_OK})

        return Response({
            "detail": details, "success": success, "status": status.HTTP_400_BAD_REQUEST})


# class LogoutView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request):
#         logout(request)
#         return Response({"detail": "Log Out Successfully", "authenticated": False, "status": status.HTTP_403_FORBIDDEN})
