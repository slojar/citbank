import datetime
import decimal
import json
import uuid
from threading import Thread

import requests
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from django.urls import reverse

from account.models import Transaction
from account.utils import get_account_balance, decrypt_text, log_request, encrypt_text
from bankone.api import bankone_get_details_by_customer_id
from citbank.exceptions import InvalidRequestException
from coporate.models import Mandate
from coporate.notifications import send_approval_notification_request, send_token_to_mandate, \
    send_successful_transfer_email

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


def get_dashboard_data(mandate):
    institution = mandate.institution
    data = get_account_balance(institution)
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
        if datetime.datetime.now() > mandate.otp_expiry:
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


def verify_approve_transfer(request, tran_req, mandate):
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
        tran_req.verified = True
        # Send email to authorizers
        for _mandate in Mandate.objects.filter(institution=mandate.institution, role__mandate_type="authorizer"):
            Thread(target=send_approval_notification_request, args=[_mandate]).start()

    if mandate.role.mandate_type == "authorizer":
        if not tran_req.verified or not tran_req.checked:
            raise InvalidRequestException({"detail": "Cannot approve, request is awaiting check or verification"})
        if tran_req.approved:
            raise InvalidRequestException({"detail": "Cannot approve, request has recently been approved"})
        tran_req.approved = True
        # Perform Transfer
        Thread(target=perform_corporate_transfer, args=[request, tran_req]).start()
        # Send email to all mandate
        for _mandates in Mandate.objects.filter(institution=mandate.institution):
            Thread(target=send_successful_transfer_email, args=[_mandates, tran_req]).start()

    tran_req.save()
    return tran_req


def generate_and_send_otp(mandate):
    # Generate random Token
    otp = str(uuid.uuid4().int)[:6]
    token = encrypt_text(otp)
    next_15_min = datetime.datetime.now() + datetime.timedelta(minutes=15)
    mandate.otp = token
    mandate.otp_expiry = next_15_min
    mandate.save()
    # Send Token to mandate
    Thread(target=send_token_to_mandate, args=[mandate, otp]).start()
    return True


def change_password_and_pin(mandate, data):
    old_password = data.get("old")
    new_password = data.get("new")
    confirm_new_password = data.get("confirm_new")

    user = mandate.user
    # Check if old password matches
    if not user.check_password(old_password):
        raise InvalidRequestException({"detail": "Old password is not valid"})

    # Validate Password Characters
    validate_password(new_password)

    if new_password != confirm_new_password:
        raise InvalidRequestException({"detail": "Password mismatch"})

    user.set_password(new_password)
    user.save()
    mandate.password_changed = True
    mandate.save()
    return True


def perform_corporate_transfer(request, trans_req):
    host = request.build_absolute_uri(reverse('account:transfer', kwargs={'bank_id': trans_req.institution.bank_id}))
    payload = json.dumps({
        "sender_type": "corporate",
        "transfer_id": trans_req.id
    })
    response = requests.post(url=host, data=payload)
    log_request(f"Transfer from corporate account ---->>> {response}")
    return True






