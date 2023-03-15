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
    customerID = models.CharField(max_length=200, null=True, blank=True)
    address = models.CharField(max_length=500)
    account_no = models.CharField(max_length=20)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    update_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.account_no}"


class Limit(models.Model):
    institution = models.OneToOneField(Institution, on_delete=models.SET_NULL, blank=True, null=True)
    daily_limit = models.DecimalField(max_digits=20, decimal_places=2, default=200000)
    transfer_limit = models.DecimalField(max_digits=20, decimal_places=2, default=100000)
    checked = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.institution.name}"


class Mandate(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    phone_number = models.CharField(max_length=11)
    bvn = models.TextField()
    password_changed = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    transaction_pin = models.TextField(blank=True, null=True)
    otp = models.TextField(blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    pin_set = models.BooleanField(default=False)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="mandate_added_by")
    created_on = models.DateTimeField(auto_now_add=True)
    update_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.role.mandate_type}"


class TransferRequest(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True)
    account_number = models.CharField(max_length=20)
    amount = models.FloatField()
    description = models.CharField(max_length=60)
    beneficiary_name = models.CharField(max_length=100)
    transfer_type = models.CharField(max_length=20)
    beneficiary_acct = models.CharField(max_length=20)
    bank_code = models.CharField(max_length=20, blank=True, null=True)
    nip_session_id = models.CharField(max_length=200, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    beneficiary_acct_type = models.CharField(max_length=20, blank=True, null=True)
    checked = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.institution.name} - {self.beneficiary_name}: {self.beneficiary_acct}, {self.amount}"





