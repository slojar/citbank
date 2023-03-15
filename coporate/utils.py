import datetime
import decimal
import json
from threading import Thread

from django.conf import settings
from django.db.models import Sum

from account.models import Transaction
from account.utils import get_account_balance, decrypt_text, get_month_start_and_end_datetime, log_request
from bankone.api import bankone_get_details_by_customer_id
from citbank.exceptions import InvalidRequestException
from coporate.models import Mandate
from coporate.notifications import send_approval_notification_request


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
    pin_set = kwargs.get("pin_set")
    transaction_pin = kwargs.get("transaction_pin")
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
            raise InvalidRequestException({"detail": "You account is not active, please contact administrator"})

    if pin_set:
        if not mandate.pin_set:
            raise InvalidRequestException({"detail": "Transaction PIN is not set"})

    if transaction_pin:
        trans_pin = decrypt_text(mandate.transaction_pin)
        if trans_pin != transaction_pin:
            raise InvalidRequestException({"detail": "Transaction PIN is not valid"})

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


def verify_approve_transfer(tran_req, mandate):
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
        # Send email to authorizers
        for _mandates in Mandate.objects.filter(institution=mandate.institution, role__mandate_type="authorizer"):
            Thread(target=send_approval_notification_request, args=[_mandates]).start()

    tran_req.save()
    return tran_req




