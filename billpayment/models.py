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

