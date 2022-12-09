from django.contrib import admin
from .models import Customer, CustomerAccount, CustomerOTP, Transaction, Beneficiary


class CustomerAccountTabularAdmin(admin.TabularInline):
    model = CustomerAccount


class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customerID', 'user', 'phone_number']
    list_filter = ['customerID', 'gender', 'active']
    inlines = [CustomerAccountTabularAdmin]


class TransactionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'transaction_type']
    list_filter = ['transaction_type', 'status', 'created_on']


admin.site.register(Customer, CustomerAdmin)
admin.site.register(Transaction, TransactionAdmin)

admin.site.register(CustomerOTP)
admin.site.register(Beneficiary)


