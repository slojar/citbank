from .models import Customer, CustomerAccount, Transaction, Beneficiary, Bank
from rest_framework import serializers
from .utils import decrypt_text


class BankSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    def get_logo(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                image = request.build_absolute_uri(obj.logo.url)
                return image
            return obj.logo.url

    class Meta:
        model = Bank
        exclude = []


class CustomerAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAccount
        exclude = []


class CustomerSerializer(serializers.ModelSerializer):
    customer_detail = serializers.SerializerMethodField()
    accounts = serializers.SerializerMethodField()
    bvn_number = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    bank = serializers.SerializerMethodField()

    def get_bank(self, obj):
        bank = None
        if obj.bank:
            bank = BankSerializer(obj.bank, context={"request": self.context.get("request")}).data
        return bank

    def get_customer_detail(self, obj):
        return obj.get_customer_detail()

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


class TransferSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()

    def get_customer(self, obj):
        return obj.customer.get_customer_detail()

    class Meta:
        model = Transaction
        exclude = []


class BeneficiarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Beneficiary
        exclude = []
