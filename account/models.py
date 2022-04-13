import uuid

from django.db import models
from django.contrib.auth.models import User


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
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name}-{self.user.last_name}"

    # def image_url(self):
    #     return str(self.image.url)


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







