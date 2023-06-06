from django.contrib import admin

from account.models import CustomerAccount
from .models import Mandate, Institution, TransferRequest, TransferScheduler, BulkUploadFile, BulkTransferRequest, Limit


class MandateInlineAdmin(admin.TabularInline):
    model = Mandate


class MandateAccountInlineAdmin(admin.TabularInline):
    model = CustomerAccount


class LimitInlineAdmin(admin.TabularInline):
    model = Limit


class InstitutionModelAdmin(admin.ModelAdmin):
    inlines = [MandateInlineAdmin, MandateAccountInlineAdmin, LimitInlineAdmin]
    list_display = ["name", "code", "account_no", "created_on"]
    search_fields = ["name", "code", "account_no"]


# admin.site.register(Role)
admin.site.register(TransferRequest)
admin.site.register(TransferScheduler)
admin.site.register(BulkUploadFile)
admin.site.register(BulkTransferRequest)
admin.site.register(Institution, InstitutionModelAdmin)

