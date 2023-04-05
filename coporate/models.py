from django.db import models
from django.contrib.auth.models import User

from account.models import Bank
from coporate.choices import MANDATE_TYPE_CHOICES, TRANSFER_REQUEST_STATUS, SCHEDULE_TYPE, \
    DAYS_OF_THE_MONTH_CHOICES, DAY_OF_THE_WEEK_CHOICES, TRANSFER_SCHEDULE_STATUS, TRANSFER_REQUEST_OPTION


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
    otp = models.TextField(blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="mandate_added_by")
    created_on = models.DateTimeField(auto_now_add=True)
    update_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.role.mandate_type}"


class TransferScheduler(models.Model):
    schedule_type = models.CharField(max_length=100, choices=SCHEDULE_TYPE, default="once")
    day_of_the_month = models.CharField(max_length=200, choices=DAYS_OF_THE_MONTH_CHOICES, blank=True, null=True)
    day_of_the_week = models.CharField(max_length=100, choices=DAY_OF_THE_WEEK_CHOICES, blank=True, null=True)
    status = models.CharField(max_length=50, choices=TRANSFER_SCHEDULE_STATUS, default="inactive")
    completed = models.BooleanField(default=False)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True)
    last_job_date = models.DateTimeField(null=True, blank=True)
    next_job_date = models.DateTimeField(null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.schedule_type}: {self.completed}"


class BulkTransferRequest(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    scheduled = models.BooleanField(default=False)
    scheduler = models.ForeignKey(TransferScheduler, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=200)
    checked = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    amount = models.FloatField(default=0.0)
    status = models.CharField(max_length=100, choices=TRANSFER_REQUEST_STATUS, default="pending")
    decline_reason = models.CharField(max_length=250, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id}: {self.checked} - InstitutionID: {self.institution_id}"


class TransferRequest(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True)
    bulk_transfer = models.ForeignKey(BulkTransferRequest, on_delete=models.SET_NULL, null=True, blank=True)
    transfer_option = models.CharField(max_length=50, choices=TRANSFER_REQUEST_OPTION, default="single")
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
    scheduled = models.BooleanField(default=False)
    scheduler = models.ForeignKey(TransferScheduler, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=100, choices=TRANSFER_REQUEST_STATUS, default="pending")
    decline_reason = models.CharField(max_length=250, blank=True, null=True)
    response_message = models.CharField(max_length=300, blank=True, null=True)
    checked = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.institution.name} - {self.beneficiary_name}: {self.beneficiary_acct}, {self.amount}"


class BulkUploadFile(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    file = models.FileField(upload_to="bulk-upload")
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.institution} - {self.file}"



