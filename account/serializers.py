from .models import Customer, CustomerAccount
from rest_framework import serializers


class CustomerAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAccount
        exclude = []


class CustomerSerializer(serializers.ModelSerializer):
    accounts = serializers.SerializerMethodField()

    def get_accounts(self, obj):
        return CustomerAccountSerializer(CustomerAccount.objects.filter(customer=obj), many=True).data

    class Meta:
        model = Customer
        exclude = []


