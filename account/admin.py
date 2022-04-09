from django.contrib import admin
from .models import Customer, CustomerAccount, CustomerOTP


class CustomerAccountTabularAdmin(admin.TabularInline):
    model = CustomerAccount


class CustomerOTPTabularAdmin(admin.TabularInline):
    model = CustomerOTP


class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customerID', 'user', 'phone_number']
    list_filter = ['customerID', 'gender', 'active']
    inlines = [CustomerAccountTabularAdmin, CustomerOTPTabularAdmin]


admin.site.register(Customer, CustomerAdmin)


