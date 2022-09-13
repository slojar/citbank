import uuid

from django.db import models
from django.contrib.auth.models import User


STATUS_CHOICES = (
    ('pending', 'Pending'), ('failed', 'Failed'), ('success', 'Success')
)

TRANSACTION_TYPE_CHOICES = (
    ('transfer', 'Transfer'), ('bill_payment', 'Bill Payment')
)

BENEFICIARY_TYPE_CHOICES = (
    ('cit_bank_transfer', 'CIT Bank Transfer'), ('other_bank_transfer', 'Other Bank Transfer'), ('airtime', 'Airtime'),
    ('data', 'Data'), ('utility', 'Utility')
)

NOTIFICATION_TYPE_CHOICES = (
    ('enquiry_email', 'Enquiry Email'), ('feedback_email', 'Feedback Email'),
    ('account_manager_rating', 'Account Manager Rating')
)


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    customerID = models.CharField(max_length=200, null=True, blank=True)
    other_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    dob = models.CharField(max_length=50, null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    bvn = models.CharField(max_length=200)
    nin = models.CharField(max_length=200, blank=True, null=True)
    transaction_pin = models.CharField(max_length=200, blank=True, null=True)
    image = models.ImageField(upload_to='profile_picture', blank=True, null=True)
    active = models.BooleanField(default=False)
    admin = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def get_customer_detail(self):
        data = dict()
        data["first_name"] = self.user.first_name
        data["last_name"] = self.user.last_name
        data["other_name"] = self.other_name
        data["email"] = self.user.email
        data["username"] = self.user.username
        data["gender"] = self.gender
        data["customer_id"] = self.customerID
        return data

    def __str__(self):
        return f"{self.user.first_name}-{self.user.last_name}"


class CustomerAccount(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account_no = models.CharField(max_length=10, null=True, blank=True)
    account_type = models.CharField(max_length=200, blank=True, null=True)
    card_no = models.CharField(max_length=200, blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.customer.user} - {self.account_no}"


class CustomerOTP(models.Model):
    phone_number = models.CharField(max_length=24, blank=True, null=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.phone_number} - {self.otp}"


class Transaction(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, blank=True, null=True)
    transaction_type = models.CharField(max_length=100, choices=TRANSACTION_TYPE_CHOICES, default='transfer')
    transaction_option = models.CharField(max_length=100, blank=True, null=True, choices=BENEFICIARY_TYPE_CHOICES)
    beneficiary_name = models.CharField(max_length=100, blank=True, null=True)
    biller_name = models.CharField(max_length=200, blank=True, null=True)
    beneficiary_number = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default='pending')
    amount = models.FloatField()
    narration = models.TextField(blank=True, null=True)
    reference = models.CharField(max_length=12, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer} - {self.reference}"


class Beneficiary(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    beneficiary_type = models.CharField(max_length=200, choices=BENEFICIARY_TYPE_CHOICES, default='')
    beneficiary_name = models.CharField(max_length=200, blank=True, null=True)
    beneficiary_bank = models.CharField(max_length=200, blank=True, null=True)
    beneficiary_acct_no = models.CharField(max_length=200, blank=True, null=True)
    beneficiary_number = models.CharField(max_length=200, blank=True, null=True)
    biller_name = models.CharField(max_length=200, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Beneficiary'
        verbose_name_plural = 'Beneficiaries'

    def __str__(self):
        return f"{self.customer}: {self.created_on}"


# class Notification(models.Model):
#     customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
#     content = models.TextField()
#     rating = models.IntegerField(default=0)
#     message_type = models.CharField(max_length=200, choices=NOTIFICATION_TYPE_CHOICES, default='enquiry_email')
#     created_on = models.DateTimeField(auto_now_add=True)
#
#     def __str__(self):
#         return f"{self.customer}-{self.message_type}"








