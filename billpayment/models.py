from django.db import models


class Airtime(models.Model):
    account_no = models.CharField(max_length=10)
    beneficiary = models.CharField(max_length=13)
    network = models.CharField(max_length=20)
    amount = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default="pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    bill_id = models.CharField(max_length=100, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_no}, ---> {self.beneficiary}"


class Data(models.Model):
    plan_id = models.CharField(max_length=100)
    account_no = models.CharField(max_length=10)
    beneficiary = models.CharField(max_length=13)
    network = models.CharField(max_length=20)
    amount = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default="pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    bill_id = models.CharField(max_length=100, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_no}, ---> {self.beneficiary}"


class CableTV(models.Model):
    service_name = models.CharField(max_length=100)
    account_no = models.CharField(max_length=10)
    smart_card_no = models.CharField(max_length=100)
    customer_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=20)
    product = models.CharField(max_length=100)
    months = models.CharField(max_length=5, help_text="Number of months subscribing for")
    amount = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default="pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_no}, ---> {self.smart_card_no}"
