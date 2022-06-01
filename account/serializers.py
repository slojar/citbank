from .models import Customer, CustomerAccount, Transaction
from rest_framework import serializers
from .utils import decrypt_text


class CustomerAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAccount
        exclude = []


class CustomerSerializer(serializers.ModelSerializer):
    accounts = serializers.SerializerMethodField()
    bvn_number = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                image = request.build_absolute_uri(obj.image.url)
                return image
            return obj.image.url

    def get_bvn_number(self, obj):
        bvn = None
        if obj.bvn:
            bvn = decrypt_text(obj.bvn)
        return bvn

    def get_accounts(self, obj):
        return CustomerAccountSerializer(CustomerAccount.objects.filter(customer=obj), many=True).data

    class Meta:
        model = Customer
        exclude = ['transaction_pin', 'nin', 'bvn']


class TransactionSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()

    def get_customer(self, obj):
        return obj.customer.get_customer_detail()

    class Meta:
        model = Transaction
        exclude = []


