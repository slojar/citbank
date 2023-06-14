from django.contrib import admin
from .models import Data, Airtime, CableTV, Electricity, BillPaymentReversal, BulkBillPayment


class BulkBillPaymentModelAdmin(admin.ModelAdmin):
    list_display = ["institution", "description", "amount", "status", "created_on"]
    list_filter = ["checked", "verified", "approved", "status"]


admin.site.register(BulkBillPayment, BulkBillPaymentModelAdmin)
admin.site.register(Data)
admin.site.register(Airtime)
admin.site.register(CableTV)
admin.site.register(Electricity)
admin.site.register(BillPaymentReversal)
