import json
from django.conf import settings
from bankone.api import bankone_get_banks
from citbank.exceptions import InvalidRequestException
from .models import Customer, CustomerAccount, Transaction, Beneficiary, Bank, AccountRequest, AccountTier, \
    TierUpgradeRequest, APPROVAL_STATUS_CHOICES
from rest_framework import serializers
from .utils import decrypt_text, format_phone_number, log_request

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
        exclude = [
            "tm_service_id", "auth_token", "institution_code", "mfb_code", "auth_key_bank_flex", "payattitude_client_id"
        ]


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
    limits = serializers.SerializerMethodField()

    def get_limits(self, obj):
        data = dict()
        tier = None
        d_limit = obj.daily_limit
        t_limit = obj.transfer_limit
        if obj.tier:
            tier = obj.tier.tier
            d_limit = obj.tier.daily_limit
            t_limit = obj.tier.transfer_limit
        data["tier"] = tier
        data["daily_limit"] = d_limit
        data["transfer_limit"] = t_limit
        return data

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
        exclude = ['transaction_pin', 'nin', 'bvn', 'user', 'daily_limit', 'transfer_limit', 'tier']


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


class AccountTierSerializerOut(serializers.ModelSerializer):
    class Meta:
        model = AccountTier
        exclude = []


class AccountTierSerializerIn(serializers.Serializer):
    daily_limit = serializers.FloatField()
    transfer_limit = serializers.FloatField()

    def update(self, instance, validated_data):
        instance.daily_limit = validated_data.get("daily_limit", instance.daily_limit)
        instance.transfer_limit = validated_data.get("transfer_limit", instance.transfer_limit)
        instance.save()
        return AccountTierSerializerOut(instance).data


class AccountTierUpgradeSerializerOut(serializers.ModelSerializer):
    class Meta:
        model = TierUpgradeRequest
        exclude = []


class AccountTierUpgradeSerializerIn(serializers.Serializer):
    auth_user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    tier_id = serializers.IntegerField()
    utility_image = serializers.ImageField()
    valid_id_image = serializers.ImageField()

    def create(self, validated_data):
        user = validated_data.get("auth_user")
        utility_bill = validated_data.get("utility_image")
        tier_id = validated_data.get("tier_id")
        valid_identity = validated_data.get("valid_id_image")

        try:
            customer = Customer.objects.get(user=user)
            bank = customer.bank
            tier = customer.tier
            new_tier = AccountTier.objects.get(id=tier_id)
        except Exception as err:
            log_request(f"AccountTierUpdate Error: {err}")
            raise InvalidRequestException({"detail": "An error has occurred, please try again later"})

        if not bank.tier_account_system:
            raise InvalidRequestException({"detail": "Tier system not enabled for customer's bank"})

        if new_tier.transfer_limit < tier.transfer_limit:
            raise InvalidRequestException({"detail": "Please select a greater tier to update to"})

        # Create Tier Upgrade Request
        tier_upgrade, _ = TierUpgradeRequest.objects.get_or_create(customer=customer, tier=new_tier)
        tier_upgrade.utility = utility_bill
        tier_upgrade.valid_id = valid_identity
        tier_upgrade.save()

        return "Request submitted successfully"


class TierUpgradeApprovalSerializerIn(serializers.Serializer):
    auth_user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    approval_status = serializers.ChoiceField(choices=APPROVAL_STATUS_CHOICES)
    rejection_reason = serializers.CharField(required=False)

    def update(self, instance, validated_data):
        user = validated_data.get("auth_user")
        approval = validated_data.get("approval_status")
        rejection_reason = validated_data.get("rejection_reason")

        if approval == "declined":
            if not rejection_reason:
                raise InvalidRequestException({"detail": "Kindly add reason for rejecting this request"})
            instance.rejected_by = user
            instance.status = "declined"
            # Send Rejection Email to customer
        elif approval == "approved":
            instance.status = "approved"
            instance.approved_by = user
            instance.customer.tier_id = instance.tier_id
            instance.customer.save()
        else:
            raise InvalidRequestException({"detail": "Approval can only be 'approved' or 'declined'"})
        instance.save()
        return AccountTierUpgradeSerializerOut(instance, context={"request": self.context.get("request")})







