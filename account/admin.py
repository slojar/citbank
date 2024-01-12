from django.contrib import admin
from .models import Customer, CustomerAccount, CustomerOTP, Transaction, Beneficiary, Bank, AccountRequest, AccountTier, \
    TierUpgradeRequest, LivenessImage


class CustomerAccountTabularAdmin(admin.TabularInline):
    model = CustomerAccount


class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customerID', 'user', 'phone_number']
    list_filter = ['gender', 'active']
    inlines = [CustomerAccountTabularAdmin]


class TransactionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'transfer_type']
    list_filter = ['transfer_type', 'status', 'created_on']


admin.site.register(Customer, CustomerAdmin)
admin.site.register(Transaction, TransactionAdmin)

admin.site.register(CustomerOTP)
admin.site.register(Beneficiary)
admin.site.register(Bank)
admin.site.register(AccountRequest)
admin.site.register(AccountTier)
admin.site.register(TierUpgradeRequest)
admin.site.register(LivenessImage)


