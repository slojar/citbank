from django.db import models
from django.contrib.auth.models import User

from account.models import Bank
from coporate.choices import MANDATE_TYPE_CHOICES


class Role(models.Model):
    mandate_type = models.CharField(max_length=100, choices=MANDATE_TYPE_CHOICES, default="uploader")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.mandate_type}"


class Institution(models.Model):
    name = models.CharField(max_length=300)
    code = models.CharField(max_length=20)
    bank = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True)
    address = models.CharField(max_length=500)
    account_no = models.CharField(max_length=20)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    update_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.account_no}"


class Mandate(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    phone_number = models.CharField(max_length=11)
    bvn = models.TextField()
    password_changed = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="mandate_added_by")
    created_on = models.DateTimeField(auto_now_add=True)
    update_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.role.mandate_type}"







