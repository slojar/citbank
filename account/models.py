import uuid

from django.db import models
from django.contrib.auth.models import User


STATUS_CHOICES = (
    ('pending', 'Pending'), ('failed', 'Failed'), ('success', 'Success')
)

TRANSFER_TYPE_CHOICES = (
    ('local_transfer', 'Local Transfer'), ('external_transfer', 'External Transfer')
)

BENEFICIARY_TYPE_CHOICES = (
    ('local_transfer', 'Local Transfer'), ('external_transfer', 'External Transfer'), ('airtime', 'Airtime'),
    ('data', 'Data'), ('utility', 'Utility')
)

NOTIFICATION_TYPE_CHOICES = (
    ('enquiry_email', 'Enquiry Email'), ('feedback_email', 'Feedback Email'),
    ('account_manager_rating', 'Account Manager Rating')
)


# class Provider(models.Model):
#     name = models.CharField(max_length=100)
#     base_url = models.CharField(max_length=200, blank=True, null=True)
#     email_api = models.CharField(max_length=200, blank=True, null=True)
#     sms_api = models.CharField(max_length=200, blank=True, null=True)
#     local_transfer_api = models.CharField(max_length=200, blank=True, null=True)
#     others_transfer_api = models.CharField(max_length=200, blank=True, null=True)
#     local_name_enquiry_api = models.CharField(max_length=200, blank=True, null=True)
#     other_name_enquiry_api = models.CharField(max_length=200, blank=True, null=True)
#     bvn_validation_api = models.CharField(max_length=200, blank=True, null=True)
#     bvn_validation_api = models.CharField(max_length=200, blank=True, null=True)


class Bank(models.Model):
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50)
    support_email = models.CharField(max_length=50)
    website = models.CharField(max_length=50)
    address = models.TextField()
    logo = models.ImageField(upload_to="bank-logo")
    active = models.BooleanField(default=False)
    tm_service_id = models.TextField(blank=True, null=True)
    # provide = models.ForeignKey(Provider, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.name


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bank = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True, blank=True)
    customerID = models.CharField(max_length=200, null=True, blank=True)
    other_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    dob = models.CharField(max_length=50, null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    bvn = models.CharField(max_length=200)
    nin = models.CharField(max_length=200, blank=True, null=True)
    transaction_pin = models.CharField(max_length=200, blank=True, null=True)
    image = models.ImageField(upload_to='profile_picture', blank=True, null=True)
    daily_limit = models.DecimalField(max_digits=20, decimal_places=2, default=200000)
    transfer_limit = models.DecimalField(max_digits=20, decimal_places=2, default=100000)
    active = models.BooleanField(default=False)
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
        data["dob"] = self.dob
        data["phone_no"] = self.phone_number
        data["customer_id"] = self.customerID
        data["staff"] = self.user.is_staff
        return data

    def get_full_name(self):
        return self.user.get_full_name()

    def __str__(self):
        return f"{self.user.first_name}-{self.user.last_name}"


class CustomerAccount(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    account_no = models.CharField(max_length=10, null=True, blank=True)
    bank_acct_number = models.CharField(max_length=200, blank=True, null=True)
    account_type = models.CharField(max_length=200, blank=True, null=True)
    card_no = models.CharField(max_length=200, blank=True, null=True)
    statement = models.FileField(null=True, blank=True, upload_to='statements')
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
    sender_acct_no = models.CharField(max_length=200, blank=True, null=True)
    transfer_type = models.CharField(max_length=100, choices=TRANSFER_TYPE_CHOICES, default='local_transfer')
    beneficiary_type = models.CharField(max_length=100, blank=True, null=True, choices=BENEFICIARY_TYPE_CHOICES)
    beneficiary_name = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=200, blank=True, null=True)
    beneficiary_acct_no = models.CharField(max_length=200, blank=True, null=True)
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









