from rest_framework.permissions import BasePermission

from coporate.models import Mandate


class IsUploader(BasePermission):
    def has_permission(self, request, view):
        try:
            mandate = Mandate.objects.get(user=request.user)
        except Mandate.DoesNotExist:
            return False
        if mandate.role.mandate_type == "uploader":
            return True
        else:
            return


class IsVerifier(BasePermission):
    def has_permission(self, request, view):
        try:
            mandate = Mandate.objects.get(user=request.user)
        except Mandate.DoesNotExist:
            return False
        if mandate.role.mandate_type == "verifier":
            return True
        else:
            return


class IsAuthorizer(BasePermission):
    def has_permission(self, request, view):
        try:
            mandate = Mandate.objects.get(user=request.user)
        except Mandate.DoesNotExist:
            return False
        if mandate.role.mandate_type == "authorizer":
            return True
        else:
            return



