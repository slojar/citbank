from django.contrib import admin
from .models import Data, Airtime, CableTV, Electricity, BillPaymentReversal, BulkBillPayment


class BulkBillPaymentModelAdmin(admin.ModelAdmin):
    list_display = ["institution", "description", "amount", "status", "created_on"]
    list_filter = ["checked", "verified", "approved", "status"]


class AirtimeModeAdmin(admin.ModelAdmin):
    list_display = ["bank", "institution", "account_no", "network", "beneficiary", "amount", "status", "created_on"]
    list_filter = ["status"]


class DataModeAdmin(admin.ModelAdmin):
    list_display = ["bank", "institution", "account_no", "network", "beneficiary", "amount", "status", "created_on"]
    list_filter = ["status"]


class CableTVModeAdmin(admin.ModelAdmin):
    list_display = ["bank", "institution", "account_no", "service_name", "customer_name", "smart_card_no", "amount",
                    "status", "created_on"]
    list_filter = ["status", "service_name"]


class ElectricityModeAdmin(admin.ModelAdmin):
    list_display = ["bank", "institution", "account_no", "disco_type", "meter_number", "status", "created_on"]
    list_filter = ["status", "disco_type"]


admin.site.register(BulkBillPayment, BulkBillPaymentModelAdmin)
admin.site.register(Data, DataModeAdmin)
admin.site.register(Airtime, AirtimeModeAdmin)
admin.site.register(CableTV, CableTVModeAdmin)
admin.site.register(Electricity, ElectricityModeAdmin)
admin.site.register(BillPaymentReversal)
