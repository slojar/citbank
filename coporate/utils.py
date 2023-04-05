import datetime
import decimal
import json
import uuid
from threading import Thread

import requests
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from account.models import Transaction, CustomerAccount
from account.utils import get_account_balance, decrypt_text, log_request, encrypt_text, get_next_date, get_next_weekday
from bankone.api import bankone_get_details_by_customer_id
from billpayment.models import Airtime, Data, CableTV, Electricity
from billpayment.serializers import AirtimeSerializer, DataSerializer, CableTVSerializer, ElectricitySerializer
from citbank.exceptions import InvalidRequestException
from coporate.models import Mandate, TransferScheduler, TransferRequest
from coporate.notifications import send_approval_notification_request, send_token_to_mandate, \
    send_successful_transfer_email

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


def get_dashboard_data(mandate):
    institution = mandate.institution
    data = get_account_balance(institution, "corporate")
    data.update({
        "institution_name": mandate.institution.name,
        "primary_account": mandate.institution.account_no,
        "first_name": mandate.user.get_full_name(),
        "bvn": decrypt_text(mandate.bvn)
    })
    return data


def check_mandate_password_pin_otp(mandate, **kwargs):
    password_changed = kwargs.get("password_changed")
    active = kwargs.get("active")
    otp = kwargs.get("otp")
    transaction_limit = kwargs.get("transaction_limit")

    if transaction_limit:
        if not mandate.institution.limit.approved:
            raise InvalidRequestException({
                "detail": "Transaction limit is yet to be approved, please reach-out to other signatories"
            })

    if password_changed:
        if not mandate.password_changed:
            raise InvalidRequestException({"detail": "You are required to change your default password"})

    if active:
        if not mandate.active:
            raise InvalidRequestException({"detail": "Your account is not active, please contact administrator"})

    if otp:
        one_time_pin = decrypt_text(mandate.otp)
        if one_time_pin != otp:
            raise InvalidRequestException({"detail": "You have entered an invalid token"})
        if timezone.now() > mandate.otp_expiry:
            raise InvalidRequestException({"detail": "Token has expired, please request a new one"})

    return True


def update_transaction_limits(request, mandate):
    daily_limit = request.data.get("daily_limit")
    transfer_limit = request.data.get("transfer_limit")

    limit = mandate.institution.limit

    if mandate.role.mandate_type == "uploader":
        if daily_limit:
            limit.daily_limit = daily_limit
        if transfer_limit:
            limit.transfer_limit = transfer_limit
        limit.checked = True
        limit.verified = False
        limit.approved = False
        # Send email to verifiers
        for mandate_ in Mandate.objects.filter(institution=mandate.institution, role__mandate_type="verifier"):
            Thread(target=send_approval_notification_request, args=[mandate_]).start()
    if mandate.role.mandate_type == "verifier":
        limit.verified = True
        # Send email to authorizers
        for _mandate in Mandate.objects.filter(institution=mandate.institution, role__mandate_type="authorizer"):
            Thread(target=send_approval_notification_request, args=[_mandate]).start()

    if mandate.role.mandate_type == "authorizer":
        if not limit.verified:
            raise InvalidRequestException({"detail": "Limit is yet to be verified"})
        limit.approved = True

    limit.save()
    return limit


def transfer_validation(mandate, amount, account_number):
    institution = mandate.institution
    today = datetime.datetime.today()
    today_trans = balance = 0
    today_date = str(today.date())
    customer_id = institution.customerID

    # Check if role_type is uploader
    if mandate.role.mandate_type != "uploader":
        raise InvalidRequestException({"detail": "Permission denied, only uploader can perform this action"})

    # Check Transfer Limit
    if decimal.Decimal(amount) > institution.limit.transfer_limit:
        log_request(f"Amount sent: {decimal.Decimal(amount)}, transfer_limit: {institution.limit.transfer_limit}")
        raise InvalidRequestException({"detail": "Amount is greater than your limit. please contact the bank"})

    current_limit = float(amount) + float(today_trans)
    today_trans = \
        Transaction.objects.filter(institution=institution, status="success", created_on=today_date).aggregate(
            Sum("amount"))["amount__sum"] or 0

    # Check Daily Transfer Limit
    if current_limit > institution.limit.daily_limit:
        log_request(f"Amount to transfer:{amount}, Total Transferred today: {today_trans}, Exceed: {current_limit}")
        raise InvalidRequestException({
            "detail": f"Your current daily transfer limit is NGN{institution.limit.daily_limit}, please contact the bank"
        })

    if institution.bank.short_name in bank_one_banks:
        # Compare amount with balance
        token = decrypt_text(institution.bank.auth_token)
        account = bankone_get_details_by_customer_id(customer_id, token).json()
        for acct in account["Accounts"]:
            if acct["NUBAN"] == account_number:
                withdraw_able = str(acct["withdrawableAmount"]).replace(",", "")
                balance = decimal.Decimal(withdraw_able)

        if balance <= 0:
            raise InvalidRequestException({"detail": "Insufficient balance"})

        if decimal.Decimal(amount) > balance:
            raise InvalidRequestException({"detail": "Amount to transfer cannot be greater than current balance"})

    return True


def verify_approve_transfer(request, tran_req, mandate, transfer_type, action=None, reject_reason=None):
    if mandate.role.mandate_type == "uploader":
        if tran_req.verified or tran_req.approved:
            raise InvalidRequestException({"detail": "Request has recently been verified or approved"})
        tran_req.checked = True
        # Send email to verifiers
        for mandate_ in Mandate.objects.filter(institution=mandate.institution, role__mandate_type="verifier"):
            Thread(target=send_approval_notification_request, args=[mandate_]).start()

    if mandate.role.mandate_type == "verifier":
        if not tran_req.checked:
            raise InvalidRequestException({"detail": "Cannot verify, request is awaiting check"})
        if tran_req.verified or tran_req.approved:
            raise InvalidRequestException({"detail": "Cannot verify, request has recently been verified or approved"})

        if action == "approve":
            tran_req.verified = True
            # Send email to authorizers
            for _mandate in Mandate.objects.filter(institution=mandate.institution, role__mandate_type="authorizer"):
                Thread(target=send_approval_notification_request, args=[_mandate]).start()
        if action == "decline":
            # Set rejection reason
            tran_req.decline_reason = reject_reason
            tran_req.status = "declined"

    if mandate.role.mandate_type == "authorizer":
        if not tran_req.verified or not tran_req.checked:
            raise InvalidRequestException({"detail": "Cannot approve, request is awaiting check or verification"})
        if tran_req.approved:
            raise InvalidRequestException({"detail": "Cannot approve, request has recently been approved"})

        if action == "approve":
            tran_req.approved = True
            tran_req.status = "approved"
            # Send email to all mandate
            for _mandates in Mandate.objects.filter(institution=mandate.institution):
                Thread(target=send_successful_transfer_email, args=[_mandates, tran_req]).start()
            if tran_req.scheduled:
                # update transfer scheduler
                scheduler = tran_req.scheduler
                scheduler.status = "active"
                scheduler.save()
            else:
                # Perform Transfer
                Thread(target=perform_corporate_transfer, args=[request, tran_req, transfer_type]).start()

        if action == "decline":
            tran_req.status = "declined"
            tran_req.decline_reason = reject_reason

    tran_req.save()
    return tran_req


def generate_and_send_otp(mandate):
    # Generate random Token
    otp = str(uuid.uuid4().int)[:6]
    token = encrypt_text(otp)
    next_15_min = timezone.now() + timezone.timedelta(minutes=15)
    mandate.otp = token
    mandate.otp_expiry = next_15_min
    mandate.save()
    # Send Token to mandate
    Thread(target=send_token_to_mandate, args=[mandate, otp]).start()
    # return True
    return otp


def change_password(mandate, data):
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    confirm_new_password = data.get("confirm_new_password")

    user = mandate.user
    # Check if old password matches
    if not user.check_password(old_password):
        raise InvalidRequestException({"detail": "Old password is not valid"})

    # Validate Password Characters
    try:
        validate_password(new_password)
    except Exception:
        raise InvalidRequestException({"detail": "Password is too short or does not meet required specification"})

    if new_password != confirm_new_password:
        raise InvalidRequestException({"detail": "Password mismatch"})

    user.set_password(new_password)
    user.save()
    mandate.password_changed = True
    # Reset OTP
    otp = str(uuid.uuid4().int)[:6]
    mandate.otp = encrypt_text(otp)
    mandate.save()
    return True


def perform_corporate_transfer(request, trans_req, transfer_type):
    if transfer_type == "bulk":
        transfer_requests = TransferRequest.objects.filter(bulk_transfer=trans_req, transfer_option="bulk")
        for trans_request in transfer_requests:
            url = request.build_absolute_uri(
                reverse('account:transfer', kwargs={'bank_id': trans_req.institution.bank_id}))
            payload = json.dumps({
                "sender_type": "corporate",
                "transfer_id": trans_request.id
            })
            response = requests.post(url=url, data=payload)
            log_request(f"Transfer from corporate account ---->>> {response}")
        return True

    host = request.build_absolute_uri(reverse('account:transfer', kwargs={'bank_id': trans_req.institution.bank_id}))
    payload = json.dumps({
        "sender_type": "corporate",
        "transfer_id": trans_req.id
    })
    response = requests.post(url=host, data=payload)
    log_request(f"Transfer from corporate account ---->>> {response}")
    return True


def scheduler_next_job(scheduler):
    present_time = timezone.datetime.now()
    next_month = get_next_date(present_time, 30)

    if scheduler.schedule_type == "daily":
        scheduler.next_job_date = get_next_date(present_time, 1)
    elif scheduler.schedule_type == "weekly":
        scheduler.next_job_date = get_next_date(present_time, 7)
        if scheduler.day_of_the_week:
            scheduler.next_job_date = get_next_weekday(present_time, scheduler.day_of_the_week)
    elif scheduler.schedule_type == "monthly":
        scheduler.next_job_date = get_next_date(present_time, 30)
        if scheduler.day_of_the_month:
            _year, _month = next_month.year, next_month.month
            try:
                day_to_run = timezone.datetime(_year, _month, scheduler.day_of_the_month)
            except Exception:
                day_to_run = timezone.datetime(_year, _month, 28)

            scheduler.next_job_date = day_to_run
    elif scheduler.schedule_type == "quarterly":
        scheduler.next_job_date = get_next_date(present_time, 90)
    elif scheduler.schedule_type == "bi-annually":
        scheduler.next_job_date = get_next_date(present_time, 180)
    elif scheduler.schedule_type == "yearly":
        scheduler.next_job_date = get_next_date(present_time, 360)
    else:
        scheduler.completed = True
    scheduler.last_job_date = present_time
    scheduler.save()

    return scheduler


def create_bulk_transfer(data, institution, bulk_trans, schedule, scheduler):
    total_amount = 0

    for item in data:
        account_no = item["account_no"]
        amount = item["amount"]
        narration = item["narration"]
        ben_name = item["beneficiary_name"]
        trans_type = item["transfer_type"]
        ben_acct_no = item["beneficiary_acct_no"]
        bank_code = item["beneficiary_bank_code"] if "beneficiary_bank_code" in item else ""
        nip_id = item["nip_session_id"] if "nip_session_id" in item else ""
        bank_name = item["beneficiary_bank_name"] if "beneficiary_bank_name" in item else ""
        ben_acct_type = item["beneficiary_acct_type"]

        TransferRequest.objects.create(
            institution=institution, bulk_transfer=bulk_trans, transfer_option="bulk", account_number=account_no,
            amount=amount, description=narration, beneficiary_name=ben_name, transfer_type=trans_type,
            beneficiary_acct=ben_acct_no, bank_code=bank_code, nip_session_id=nip_id, bank_name=bank_name,
            beneficiary_acct_type=ben_acct_type, scheduled=schedule, scheduler=scheduler
        )
        total_amount += float(amount)
    bulk_trans.amount = total_amount
    bulk_trans.save()
    return True


def check_balance_for_bill_payment(institution, account_no, amount, payment_type):
    code = str(uuid.uuid4().int)[:5]
    ref_no = ""
    if institution.bank.short_name in bank_one_banks:
        bank_s_name = str(institution.bank.short_name).upper()
        token = decrypt_text(institution.bank.auth_token)
        ref_no = f"{bank_s_name}-{code}"

        if not CustomerAccount.objects.filter(institution=institution, account_no=account_no).exists():
            return False, "Account is not found, or does not belong to institution", ""

        # Check available balance
        if payment_type == ("cable_tv" or "electricity"):
            amount = decimal.Decimal(amount) + institution.bank.bill_payment_charges

        balance = 0
        response = bankone_get_details_by_customer_id(institution.customerID, token).json()
        accounts = response["Accounts"]

        for account in accounts:
            if account["NUBAN"] == str(account_no):
                balance = str(account["withdrawableAmount"]).replace(",", "")

        if float(balance) <= 0:
            return False, "Insufficient balance", ""

        if float(amount) > float(balance):
            return False, "Amount cannot be greater than current balance", ""

    return True, "Success", ref_no


def create_bill_payment(data, acct_no, phone, amount, payment_type, company, ref_no, option=None, bulk_instance=None):
    network = data.get("network")
    phone = f"234{phone[-10:]}"

    if payment_type == "airtime":
        if not network:
            raise InvalidRequestException({"detail": "Please select a mobile network"})

        instance = Airtime.objects.create(
            institution=company, account_no=acct_no, beneficiary=phone, network=network,
            amount=amount, reference=ref_no, transaction_type="corporate", bank=company.bank
        )
        serializer = AirtimeSerializer(instance).data

    elif payment_type == "data":
        plan_id = data.get("plan_id")
        if not (plan_id and network):
            raise InvalidRequestException({"detail": "Please select valid network and plan"})

        instance = Data.objects.create(
            institution=company, account_no=acct_no, beneficiary=phone, network=network,
            amount=amount, reference=ref_no, transaction_type="corporate", plan_id=plan_id, bank=company.bank
        )
        serializer = DataSerializer(instance).data

    elif payment_type == "cable_tv":
        service_name = data.get("service_name")
        duration = data.get("duration")
        customer_name = data.get("customer_name", "")
        product_codes = data.get("product_codes")
        smart_card_no = data.get("smart_card_no")

        if not all([service_name, duration, product_codes, smart_card_no]):
            raise InvalidRequestException(
                {"detail": "Service name, duration, product code and smart cart number are required"}
            )

        instance = CableTV.objects.create(
            bank=company.bank, institution=company, transaction_type="corporate", service_name=service_name,
            account_no=acct_no, smart_card_no=smart_card_no, customer_name=customer_name,
            phone_number=phone, product=product_codes, months=duration, amount=amount, reference=ref_no
        )
        serializer = CableTVSerializer(instance).data

    elif payment_type == "electricity":
        disco_type = data.get("disco_type")
        meter_no = data.get("meter_no")

        if not all([disco_type, meter_no]):
            raise InvalidRequestException({"detail": "Disco type and meter number are required"})

        instance = Electricity.objects.create(
            bank=company.bank, institution=company, transaction_type="corporate", account_no=acct_no,
            disco_type=disco_type, meter_number=meter_no, amount=amount, phone_number=phone, reference=ref_no
        )
        serializer = ElectricitySerializer(instance).data

    else:
        raise InvalidRequestException({"detail": "Please select a valid payment type"})

    if option == "bulk":
        instance.transaction_option = "bulk"
        instance.bulk_payment = bulk_instance
        instance.save()

    return serializer


def retrieve_bill_payment(payment_type, company, pk=None):
    option = "single"
    trans_type = "corporate"
    if payment_type == "airtime":
        if pk:
            instance = get_object_or_404(
                Airtime, id=pk, institution=company, transaction_option=option, transaction_type=trans_type
            )
            serializer = AirtimeSerializer(instance).data
        else:
            serializer = AirtimeSerializer(
                Airtime.objects.filter(institution=company, transaction_option=option, transaction_type=trans_type
                                       ), many=True).data

    elif payment_type == "data":
        if pk:
            instance = get_object_or_404(
                Data, id=pk, institution=company, transaction_option=option, transaction_type=trans_type
            )
            serializer = DataSerializer(instance).data
        else:
            serializer = DataSerializer(
                Data.objects.filter(institution=company, transaction_option=option, transaction_type=trans_type
                                    ), many=True).data

    elif payment_type == "cable_tv":
        if pk:
            instance = get_object_or_404(
                CableTV, id=pk, institution=company, transaction_option=option, transaction_type=trans_type
            )
            serializer = CableTVSerializer(instance).data
        else:
            serializer = CableTVSerializer(
                CableTV.objects.filter(institution=company, transaction_option=option, transaction_type=trans_type
                                       ), many=True).data

    elif payment_type == "electricity":
        if pk:
            instance = get_object_or_404(
                Electricity, id=pk, institution=company, transaction_option=option, transaction_type=trans_type
            )
            serializer = ElectricitySerializer(instance).data
        else:
            serializer = ElectricitySerializer(
                Electricity.objects.filter(institution=company, transaction_option=option, transaction_type=trans_type
                                           ), many=True).data

    else:
        raise InvalidRequestException({"detail": "Please select a valid payment type"})

    return serializer
