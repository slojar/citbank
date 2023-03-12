from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from citbank.exceptions import raise_serializer_error_msg, InvalidRequestException
from coporate.models import Mandate
from coporate.serializers import MandateSerializerOut


class MandateLoginAPIView(APIView):
    permission_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not all([username, password]):
            raise InvalidRequestException({"detail": "Username and password required"})

        # Check user is valid
        user = authenticate(username=username, password=password)

        if not user:
            raise InvalidRequestException({"detail": "Invalid username or password"})

        mandate = get_object_or_404(Mandate, user=user)
        # Check password change
        if not mandate.password_changed:
            raise InvalidRequestException({"detail": "Kindly change your default password to continue"})
        # Check active status
        if not mandate.active:
            raise InvalidRequestException({"detail": "Your account is not active, please contact admin for support"})

        serializer = MandateSerializerOut(mandate, context={"request": request}).data
        return Response({
            "detail": "Login Successful", "access_token": str(AccessToken.for_user(request.user)),
            "refresh_token": str(RefreshToken.for_user(request.user)), "data": serializer
        })



