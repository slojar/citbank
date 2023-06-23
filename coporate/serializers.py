import csv
import decimal
import json
import uuid
from io import StringIO
from threading import Thread

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from account.utils import decrypt_text, encrypt_text, log_request
from bankone.api import bankone_others_name_query, bankone_get_account_by_account_no
from billpayment.models import BulkBillPayment
from citbank.exceptions import InvalidRequestException
from .models import Mandate, Institution, Limit, TransferRequest, TransferScheduler, BulkUploadFile, \
    BulkTransferRequest
from .notifications import send_username_password_to_mandate
from .utils import transfer_validation, create_bulk_transfer, create_bill_payment


class MandateSerializerIn(serializers.Serializer):
    institution_id = serializers.IntegerField()
    level = serializers.IntegerField()
    bvn = serializers.CharField(min_length=11, max_length=11)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.CharField()

    def create(self, validated_data):
        institution_id = validated_data.get("institution_id")
        level = validated_data.get("level")
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

        institution = Institution.objects.get(id=institution_id)

        if Mandate.objects.filter(institution=institution, user__email__iexact=email).exists():
            raise InvalidRequestException({"detail": "Signatory with this email already exist"})

        if Mandate.objects.filter(institution=institution, phone_number=phone_no).exists():
            raise InvalidRequestException({"detail": "Signatory with this phone number already exist"})

        if level not in range(1, 4):
            raise InvalidRequestException({"detail": "Invalid level input"})

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
            user=user, institution=institution, bvn=encrypted_bvn, level=level, phone_number=phone_no,
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
    # role = serializers.CharField(source="role.mandate_type")
    added_by = serializers.CharField(source="added_by.last_name")
    bvn = serializers.SerializerMethodField()
    other_signatories = serializers.SerializerMethodField()
    limit = serializers.SerializerMethodField()

    def get_other_signatories(self, obj):
        data = None
        if Mandate.objects.filter(institution=obj.institution).exists():
            data = [{
                "name": mandate.user.get_full_name(),
                "level": mandate.level,
                "email": mandate.user.email,
                "phone_number": mandate.phone_number,
                "active": mandate.active
            } for mandate in Mandate.objects.filter(institution=obj.institution)]
        return data

    def get_bvn(self, obj):
        if obj.bvn:
            return decrypt_text(obj.bvn)
        return None

    def get_limit(self, obj):
        data = dict()
        if Limit.objects.filter(institution_id=obj.institution_id).exists():
            limit = Limit.objects.filter(institution_id=obj.institution_id).last()
            data["id"] = limit.id
            data["daily_transfer_limit"] = limit.daily_limit
            data["total_transfer_limit"] = limit.transfer_limit
        return data

    class Meta:
        model = Mandate
        exclude = ["user", "otp", "otp_expiry"]
        depth = 1


# class RoleSerializerIn(serializers.Serializer):
#     mandate_type = serializers.CharField()


# class RoleSerializerOut(serializers.ModelSerializer):
#     class Meta:
#         model = Role
#         exclude = []


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

        # Create Limit
        limit, _ = Limit.objects.get_or_create(institution=institution)

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
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = Limit
        exclude = []


class TransferRequestSerializerOut(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = TransferRequest
        exclude = []


class TransferRequestSerializerIn(serializers.Serializer):
    current_user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    account_no = serializers.CharField()
    amount = serializers.FloatField(required=False)
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

        if transfer_type == "single" and not account_number:
            raise InvalidRequestException({"detail": "Account number is required"})

        # Create Transfer Request
        trans_req = TransferRequest.objects.create(
            institution=mandate.institution, account_no=account_number, amount=amount, description=description,
            beneficiary_name=beneficiary_name, transfer_type=transfer_type, beneficiary_acct=beneficiary_acct,
            bank_code=bank_code, nip_session_id=nip_session_id, bank_name=bank_name, transfer_option="single",
            beneficiary_acct_type=beneficiary_acct_type
        )

        if schedule:
            if not all([schedule_type, start_date, end_date]):
                raise InvalidRequestException({"detail": "schedule type, start date and end date are not selected"})
            # Create TransferScheduler
            scheduler = TransferScheduler.objects.create(
                schedule_type=schedule_type, day_of_the_month=day_of_the_month, day_of_the_week=day_of_the_week,
                start_date=start_date, end_date=end_date, transfer_option=transfer_type
            )
            trans_req.scheduled = True
            trans_req.scheduler = scheduler
            trans_req.save()

        return TransferRequestSerializerOut(trans_req, context={"request": self.context.get("request")}).data


class TransferSchedulerSerializerOut(serializers.ModelSerializer):
    total_amount = serializers.SerializerMethodField()
    transfers = serializers.SerializerMethodField()

    def get_total_amount(self, obj):
        return TransferRequest.objects.filter(scheduler=obj).aggregate(Sum("amount"))["amount__sum"] or 0

    def get_transfers(self, obj):
        return TransferRequestSerializerOut(TransferRequest.objects.filter(scheduler=obj), many=True).data

    class Meta:
        model = TransferScheduler
        exclude = []


class BulkUploadFileSerializerIn(serializers.Serializer):
    current_user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    file = serializers.FileField()

    def create(self, validated_data):
        user = validated_data.get('current_user')
        file = validated_data.get("file")

        institution = user.mandate.institution
        upload = BulkUploadFile.objects.create(institution=institution, file=file)
        file = upload.file.read().decode('utf-8', 'ignore')
        read = csv.reader(StringIO(file), delimiter=",")
        next(read)

        bank = institution.bank
        bank_one_banks = json.loads(settings.BANK_ONE_BANKS)
        short_name = bank.short_name
        decrypted_token = decrypt_text(bank.auth_token)

        ne_success = list()
        ne_failed = list()

        for row in read:
            try:
                debit_account_number = row[0]
                amount = row[1]
                description = row[2]
                credit_account_number = row[3]
                credit_bank_code = row[4]
                credit_bank_name = row[5]
                transfer_type = str(row[6]).lower()
                credit_account_type = row[7]

                data = dict()
                data["account_no"] = debit_account_number
                data["amount"] = amount
                data["narration"] = description
                data["beneficiary_acct_no"] = credit_account_number
                data["beneficiary_acct_type"] = credit_account_type

                if transfer_type == "samebank":
                    # Do local name enquiry
                    if short_name in bank_one_banks:
                        response = bankone_get_account_by_account_no(credit_account_number, decrypted_token).json()
                        if "CustomerDetails" in response:
                            customer_detail = response["CustomerDetails"]
                            data["beneficiary_name"] = customer_detail["Name"]
                            data["transfer_type"] = "same_bank"
                            ne_success.append(data)
                        else:
                            ne_failed.append(data)
                else:
                    # Do external name enquiry
                    if short_name in bank_one_banks:
                        response = bankone_others_name_query(credit_account_number, credit_bank_code, decrypted_token)
                        if "IsSuccessful" in response and response["IsSuccessful"] is True:
                            data["beneficiary_name"] = response["Name"]
                            data["nip_session_id"] = response["SessionID"]
                            data["transfer_type"] = "other_bank"
                            data["beneficiary_bank_code"] = credit_bank_code
                            data["beneficiary_bank_name"] = credit_bank_name
                            ne_success.append(data)
                        else:
                            ne_failed.append(data)

            except Exception as ex:
                log_request(f"Error while reading bulk upload file: {ex}")

        # Update uploaded file
        upload.used = True
        upload.save()

        return {"success": ne_success, "failed": ne_failed}


class BulkUploadBillSerializerIn(serializers.Serializer):
    file = serializers.FileField()
    narration = serializers.CharField(max_length=198)
    current_user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    def create(self, validated_data):
        user = validated_data.get('current_user')
        file = validated_data.get("file")
        narration = validated_data.get("narration")

        upload = BulkUploadFile.objects.create(institution=user.mandate.institution, file=file)
        file = upload.file.read().decode('utf-8', 'ignore')
        read = csv.reader(StringIO(file), delimiter=",")
        next(read)

        institution = user.mandate.institution
        bank = institution.bank
        bank_one_banks = json.loads(settings.BANK_ONE_BANKS)
        short_name = bank.short_name
        ref_no = ""

        # create BulkBillPayment
        bulk_bill = BulkBillPayment.objects.create(institution=institution, description=narration)
        total_amount = 0
        for row in read:
            try:
                debit_account_number = row[0]
                amount = row[1]
                network = row[2]
                phone_number = row[3]

                data = {"network": network}
                code = str(uuid.uuid4().int)[:5]
                if short_name in bank_one_banks:
                    bank_s_name = str(short_name).upper()
                    ref_no = f"{bank_s_name}-{code}"

                # create airtime instances
                create_bill_payment(
                    data, debit_account_number, phone_number, amount, "airtime", institution, ref_no, option="bulk",
                    bulk_instance=bulk_bill
                )
                total_amount += decimal.Decimal(amount)

            except Exception as ex:
                log_request(f"Error while reading bulk upload file: {ex}")

        # Update uploaded file
        bulk_bill.amount = total_amount
        bulk_bill.save()
        upload.used = True
        upload.save()

        return BulkPaymentSerializerOut(bulk_bill).data


class BulkPaymentSerializerOut(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = BulkBillPayment
        exclude = []


class BulkTransferSerializerOut(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()
    declined_by = serializers.SerializerMethodField()

    def get_approved_by(self, obj):
        if obj.approved_by:
            data = [signatory.user.get_full_name() for signatory in obj.approved_by.all()]
            return data
        return []

    def get_declined_by(self, obj):
        if obj.declined_by:
            data = [signatory.user.get_full_name() for signatory in obj.declined_by.all()]
            return data
        return []

    class Meta:
        model = BulkTransferRequest
        exclude = []


class BulkTransferSerializerIn(serializers.Serializer):
    current_user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    data = serializers.ListField(child=serializers.DictField())
    schedule = serializers.BooleanField(required=False)
    description = serializers.CharField(max_length=190)

    schedule_type = serializers.CharField(required=False)
    day_of_the_month = serializers.CharField(required=False)
    day_of_the_week = serializers.CharField(required=False)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)

    def create(self, validated_data):
        user = validated_data.get('current_user')
        data = validated_data.get("data")
        description = validated_data.get("description")
        schedule = validated_data.get("schedule", False)

        schedule_type = validated_data.get("schedule_type")
        day_of_the_month = validated_data.get("day_of_the_month")
        day_of_the_week = validated_data.get("day_of_the_week")
        start_date = validated_data.get("start_date")
        end_date = validated_data.get("end_date")

        if user.mandate.level != 1:
            raise InvalidRequestException({"detail": "You are not permitted to perform this action"})

        institution = user.mandate.institution
        scheduler = None
        # Create Bulk Transfer Request
        bulk_trans = BulkTransferRequest.objects.create(institution=institution, description=description)

        if schedule and not all([schedule_type, start_date, end_date]):
            raise InvalidRequestException({"detail": "schedule type, start date and end date are not selected"})

        if schedule:
            # Create TransferScheduler
            scheduler = TransferScheduler.objects.create(
                schedule_type=schedule_type, day_of_the_month=day_of_the_month, day_of_the_week=day_of_the_week,
                start_date=start_date, end_date=end_date, transfer_option="bulk"
            )
            bulk_trans.scheduler = scheduler
            bulk_trans.save()
        # Create Transfer Requests
        Thread(target=create_bulk_transfer, args=[data, institution, bulk_trans, schedule, scheduler]).start()

        return BulkTransferSerializerOut(bulk_trans).data





