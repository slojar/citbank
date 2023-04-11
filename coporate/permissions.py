from rest_framework.permissions import BasePermission
from coporate.models import Mandate


class IsUploader(BasePermission):
    def has_permission(self, request, view):
        try:
            mandate = Mandate.objects.get(user=request.user)
        except Mandate.DoesNotExist:
            return False
        if mandate.level == 1:
            return True
        else:
            return


class IsMandate(BasePermission):
    def has_permission(self, request, view):
        try:
            Mandate.objects.get(user=request.user)
            return True
        except Mandate.DoesNotExist:
            return False



