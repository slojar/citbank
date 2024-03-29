from django.db import models

REVERSAL_STATUS = (
    ("completed", "Completed"), ("pending", "Pending")
)


class Airtime(models.Model):
    account_no = models.CharField(max_length=10)
    beneficiary = models.CharField(max_length=13)
    network = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default="pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    bill_id = models.CharField(max_length=100, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_no}, ---> {self.beneficiary}"


class Data(models.Model):
    plan_id = models.CharField(max_length=100)
    account_no = models.CharField(max_length=10)
    beneficiary = models.CharField(max_length=13)
    network = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default="pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
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
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default="pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_no}, ---> {self.smart_card_no}"


class Electricity(models.Model):
    account_no = models.CharField(max_length=10)
    disco_type = models.CharField(max_length=50)
    meter_number = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    phone_number = models.CharField(max_length=20)
    token = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, default="pending")
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    bill_id = models.CharField(max_length=100, blank=True, null=True)
    token_sent = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_no}, {self.disco_type} -----> {self.meter_number} - {self.amount}"


class BillPaymentReversal(models.Model):
    transaction_date = models.CharField(max_length=50)
    transaction_reference = models.CharField(max_length=50)
    payment_type = models.CharField(max_length=50, default="airtime")
    status = models.CharField(max_length=50, choices=REVERSAL_STATUS, default="pending")
    ref = models.CharField(max_length=100, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_date} - {self.transaction_reference}, {self.status}"
