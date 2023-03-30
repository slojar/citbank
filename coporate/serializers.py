import uuid
from threading import Thread

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from account.models import Bank
from account.utils import decrypt_text, encrypt_text
from citbank.exceptions import InvalidRequestException
from .models import Mandate, Institution, Role, Limit, TransferRequest, TransferScheduler
from .notifications import send_username_password_to_mandate
from .utils import transfer_validation


class MandateSerializerIn(serializers.Serializer):
    institution_id = serializers.IntegerField()
    role_id = serializers.IntegerField()
    bvn = serializers.CharField(min_length=11, max_length=11)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField()

    def create(self, validated_data):
        institution_id = validated_data.get("institution_id")
        role_id = validated_data.get("role_id")
        bvn = validated_data.get("bvn")
        first_name = validated_data.get("first_name")
        last_name = validated_data.get("last_name")
        email = validated_data.get("email")
        phone_number = validated_data.get("phone_number")

        request = self.context.get("request")
        admin_bank = request.user.customer.bank
        encrypted_bvn = encrypt_text(bvn)

        # Reformat phone number
        phone_no = f"0{phone_number[-10:]}"

        # Check if institution exist
        if not Institution.objects.filter(id=institution_id, bank=admin_bank).exists():
            raise InvalidRequestException({"detail": "Selected institution is not valid"})

        # Check if role is valid
        if not Role.objects.filter(id=role_id).exists():
            raise InvalidRequestException({"detail": "Please select a valid role"})

        institution = Institution.objects.get(id=institution_id)
        role = Role.objects.get(id=role_id)

        # Generate username from institution code
        inst_code = institution.code
        num = str(uuid.uuid4().int)[:3]
        username = f"{inst_code}/{last_name}{num}"
        # Generate random password
        random_password = User.objects.make_random_password(length=10)

        # Create user
        user = User.objects.create(first_name=first_name, last_name=last_name, username=username)
        user.email = email
        user.set_password(random_password)
        user.save()

        # Create mandate
        mandate = Mandate.objects.create(
            user=user, institution=institution, bvn=encrypted_bvn, role=role, phone_number=phone_no,
            added_by=request.user
        )

        # Send username and password to customer
        Thread(target=send_username_password_to_mandate, args=[mandate, random_password]).start()

        # To be removed later
        from account.utils import log_request
        log_request(f"Username: {username}\nPassword: {random_password}")
        return MandateSerializerOut(mandate, context=self.context).data


class MandateSerializerOut(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    email = serializers.CharField(source="user.email")
    role = serializers.CharField(source="role.mandate_type")
    added_by = serializers.CharField(source="added_by.last_name")
    bvn = serializers.SerializerMethodField()
    other_signatories = serializers.SerializerMethodField()

    def get_other_signatories(self, obj):
        data = None
        if Mandate.objects.filter(institution=obj.institution).exists():
            data = [{
                "name": mandate.user.get_full_name(),
                "role": mandate.role.mandate_type,
                "email": mandate.user.email,
                "phone_number": mandate.phone_number,
                "active": mandate.active
            } for mandate in Mandate.objects.filter(institution=obj.institution).exclude(id=obj.id)]
        return data

    def get_bvn(self, obj):
        if obj.bvn:
            return decrypt_text(obj.bvn)
        return None

    class Meta:
        model = Mandate
        exclude = ["user"]
        depth = 1


class RoleSerializerIn(serializers.Serializer):
    mandate_type = serializers.CharField()


class RoleSerializerOut(serializers.ModelSerializer):
    class Meta:
        model = Role
        exclude = []


class InstitutionSerializerIn(serializers.Serializer):
    name = serializers.CharField()
    customer_id = serializers.CharField()
    code = serializers.CharField()
    address = serializers.CharField()
    account_no = serializers.CharField()

    def create(self, validated_data):
        name = validated_data.get("name")
        customer_id = validated_data.get("customer_id")
        code = validated_data.get("code")
        address = validated_data.get("address")
        account_no = validated_data.get("account_no")

        # Check if Institution name or code exist
        if Institution.objects.filter(name__iexact=name).exists():
            raise InvalidRequestException({"detail": "Institution name is already taken"})
        if Institution.objects.filter(code__iexact=code).exists():
            raise InvalidRequestException({"detail": "Institution code is already registered with another institution"})

        request = self.context.get("request")
        bank = request.user.customer.bank

        # Create Institution
        institution, created = Institution.objects.get_or_create(name=name, code=code, bank=bank, customerID=customer_id)
        institution.address = address
        institution.account_no = account_no
        institution.created_by = request.user
        institution.save()

        return InstitutionSerializerOut(institution, context=self.context).data


class InstitutionSerializerOut(serializers.ModelSerializer):
    mandates = serializers.SerializerMethodField()
    created_by = serializers.CharField(source="created_by.first_name")

    def get_mandates(self, obj):
        if Mandate.objects.filter(institution=obj).exists():
            return MandateSerializerOut(Mandate.objects.filter(institution=obj), many=True).data
        return None

    class Meta:
        model = Institution
        exclude = []


class LimitSerializerOut(serializers.ModelSerializer):
    class Meta:
        model = Limit
        exclude = []


class TransferRequestSerializerOut(serializers.ModelSerializer):
    class Meta:
        model = TransferRequest
        exclude = []


class TransferRequestSerializerIn(serializers.Serializer):
    current_user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    account_no = serializers.CharField()
    amount = serializers.FloatField()
    narration = serializers.CharField(max_length=60)
    beneficiary_name = serializers.CharField(max_length=100)
    transfer_type = serializers.CharField()
    beneficiary_acct_no = serializers.CharField()
    beneficiary_bank_code = serializers.CharField(required=False)
    nip_session_id = serializers.CharField(required=False)
    beneficiary_bank_name = serializers.CharField(required=False)
    beneficiary_acct_type = serializers.CharField(required=False)
    schedule = serializers.BooleanField(required=False)

    schedule_type = serializers.CharField(required=False)
    day_of_the_month = serializers.CharField(required=False)
    day_of_the_week = serializers.CharField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)

    def create(self, validated_data):
        user = validated_data.get('current_user')
        account_number = validated_data.get("account_no")
        amount = validated_data.get("amount")
        description = validated_data.get("narration")
        beneficiary_name = validated_data.get("beneficiary_name")
        transfer_type = validated_data.get("transfer_type")
        beneficiary_acct = validated_data.get("beneficiary_acct_no")
        bank_code = validated_data.get("beneficiary_bank_code")
        nip_session_id = validated_data.get("nip_session_id")
        bank_name = validated_data.get("beneficiary_bank_name")
        beneficiary_acct_type = validated_data.get("beneficiary_acct_type")

        schedule = validated_data.get('schedule', False)
        schedule_type = validated_data.get("schedule_type")
        day_of_the_month = validated_data.get("day_of_the_month")
        day_of_the_week = validated_data.get("day_of_the_week")
        start_date = validated_data.get("start_date")
        end_date = validated_data.get("end_date")

        mandate = get_object_or_404(Mandate, user=user)
        transfer_validation(mandate, amount, account_number)

        # Create Transfer Request
        trans_req = TransferRequest.objects.create(
            institution=mandate.institution, account_number=account_number, amount=amount, description=description,
            beneficiary_name=beneficiary_name, transfer_type=transfer_type, beneficiary_acct=beneficiary_acct,
            bank_code=bank_code, nip_session_id=nip_session_id, bank_name=bank_name,
            beneficiary_acct_type=beneficiary_acct_type
        )

        if schedule:
            if not all([schedule_type, start_date, end_date]):
                raise InvalidRequestException({"detail": "schedule type, start date and end date are not selected"})
            # Create TransferScheduler
            scheduler = TransferScheduler.objects.create(
                schedule_type=schedule_type, day_of_the_month=day_of_the_month, day_of_the_week=day_of_the_week,
                start_date=start_date, end_date=end_date
            )
            trans_req.scheduled = True
            trans_req.scheduler = scheduler
            trans_req.save()

        return TransferRequestSerializerOut(trans_req, context={"request": self.context.get("request")}).data


class TransferSchedulerSerializerOut(serializers.ModelSerializer):
    transfers = serializers.SerializerMethodField()

    def get_transfers(self, obj):
        return TransferRequestSerializerOut(TransferRequest.objects.filter(scheduler=obj), many=True).data

    class Meta:
        model = TransferScheduler
        exclude = []


