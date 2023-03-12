import uuid
from threading import Thread

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from account.models import Bank
from account.utils import decrypt_text, encrypt_text
from citbank.exceptions import InvalidRequestException
from .models import Mandate, Institution, Role
from .notifications import send_username_password_to_mandate


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

        # Check if user already exist
        if User.objects.filter(email__iexact=email).exists():
            raise InvalidRequestException({"detail": "User with this email already exist"})

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
    code = serializers.CharField()
    address = serializers.CharField()
    account_no = serializers.CharField()

    def create(self, validated_data):
        name = validated_data.get("name")
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
        institution, created = Institution.objects.get_or_create(name=name, code=code, bank=bank)
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



