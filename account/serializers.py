import json
from django.conf import settings
from bankone.api import bankone_get_banks
from .models import Customer, CustomerAccount, Transaction, Beneficiary, Bank, AccountRequest
from rest_framework import serializers
from .utils import decrypt_text, format_phone_number

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


class BankSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()
    nip_banks = serializers.SerializerMethodField()

    def get_logo(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                image = request.build_absolute_uri(obj.logo.url)
                return image
            return obj.logo.url

    def get_nip_banks(self, obj):
        result = list()
        if obj.short_name in bank_one_banks:
            token = decrypt_text(obj.auth_token)
            response = bankone_get_banks(token)
            for res in response:
                data = dict()
                data["bank_name"] = res["Name"]
                data["bank_code"] = res["Code"]
                result.append(data)
        return result

    class Meta:
        model = Bank
        exclude = ["tm_service_id", "auth_token", "institution_code", "mfb_code", "auth_key_bank_flex"]


class CustomerAccountSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()

    def get_customer_name(self, obj):
        return obj.customer.get_full_name()

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
        exclude = ['transaction_pin', 'nin', 'bvn', 'user']


class TransferSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    institution = serializers.SerializerMethodField()

    def get_customer(self, obj):
        if obj.customer:
            return obj.customer.get_customer_detail()
        return None

    def get_institution(self, obj):
        if obj.institution:
            return obj.institution.name
        return None

    class Meta:
        model = Transaction
        exclude = ["fee", "channel"]


class BeneficiarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Beneficiary
        exclude = []


class AccountRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountRequest
        exclude = []


class ValidatePhoneSerializerIn(serializers.Serializer):
    phone = serializers.CharField()

    def create(self, validated_data):
        phone_number = validated_data.get("phone")
        ph_no = format_phone_number(phone_number)
        try:
            name = Customer.objects.get(phone_number=ph_no).get_full_name()
            accounts = [
                str(account.account_no) for account in
                CustomerAccount.objects.filter(customer__phone_number=ph_no)
            ]
            data = {
                "Status": "00",
                "Success": True,
                "Name": name,
                "Account": ",".join(accounts)
            }
        except Exception:
            data = {
                "Status": "Phone not found",
                "Success": "Declined",
                "Name": "",
                "Account": ""
            }

        return json.dumps(data)


