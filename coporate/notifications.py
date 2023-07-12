import json
from account.utils import decrypt_text
from bankone.api import bankone_send_email, bankone_send_sms
from django.conf import settings

from coporate.utils import check_upper_level_exist

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


def send_email_to_bankone_mandates(bank, sender, email, subject, content):
    inst_code = decrypt_text(bank.institution_code)
    mfb_code = decrypt_text(bank.mfb_code)
    # Send Email
    bankone_send_email(sender, email, subject, content, inst_code, mfb_code)
    return True


def send_sms_to_bankone_mandates(bank, account_no, content, receiver):
    code = decrypt_text(bank.institution_code)
    token = decrypt_text(bank.auth_token)
    bankone_send_sms(account_no, content, receiver, token, code, bank.short_name)
    return True


def send_username_password_to_mandate(mandate, password):
    first_name = mandate.user.first_name
    institution = mandate.institution
    account_no = institution.account_no
    receiver = mandate.phone_number
    bank = institution.bank
    bank_name = bank.name
    sender = bank.support_email
    subject = "Corporate Account (On-boarding)"
    username = mandate.user.username
    email = mandate.user.email
    short_name = bank.short_name
    content = f"Dear {first_name},<br><br>Please find below, your username and password for your corporate account " \
              f"opened at {bank_name}.<br><br>Username: <strong>{username}</strong><br>" \
              f"Password: <strong>{password}</strong><br>" \
              f"CustomerID: <strong>{institution.customerID}</strong><br><br>" \
              f"Kindly change your password upon successful login.<br>" \
              f"<br>Regards, <br>{bank_name} Team."
    sms_content = f"Dear {first_name},\nPlease login with the following credentials " \
                  f"\nUsername: {username}\nPassword: {password}\n" \
                  f"CustomerID: {institution.customerID}\n\nKindly change your password upon successful login.\n" \
                  f"\nRegards,\n{bank_name} Team."
    if short_name in bank_one_banks:
        send_email_to_bankone_mandates(bank, sender, email, subject, content)
        send_sms_to_bankone_mandates(bank, account_no, sms_content, receiver)
    return True


def send_otp_to_mandate(mandate):
    bank = mandate.institution.bank
    bank_name = bank.name
    first_name = mandate.user.first_name
    subject = "One Time Transaction PIN"
    email = mandate.user.email
    sender = bank.support_email
    one_time_pin = decrypt_text(mandate.otp)
    short_name = bank.short_name
    content = f"Dear {first_name},<br><br>Kindly use the following Token to complete your transaction, " \
              f"Token: <strong>{one_time_pin}</strong><br>" \
              f"<br>Regards, <br>{bank_name} Team."
    if short_name in bank_one_banks:
        send_email_to_bankone_mandates(bank, sender, email, subject, content)
    return True


def send_approval_notification_request(mandate):
    upper_level = check_upper_level_exist(mandate)
    action = "authorize"
    if not upper_level:
        action = "verify"
    subject = "Transaction Approval Request"
    first_name = mandate.user.first_name
    bank = mandate.institution.bank
    email = mandate.user.email
    bank_name = bank.name
    sender = bank.support_email
    short_name = bank.short_name
    content = f"Dear {first_name},<br><br>An approval request has been submitted. " \
              f"<br>Kindly login to your dashboard to {action} transaction.<br>" \
              f"<br>Regards, <br>{bank_name} Team."
    if short_name in bank_one_banks:
        send_email_to_bankone_mandates(bank, sender, email, subject, content)
    return True


def send_token_to_mandate(mandate, otp):
    first_name = mandate.user.first_name
    subject = "Transaction Token"
    bank = mandate.institution.bank
    account_no = mandate.institution.account_no
    receiver = mandate.phone_number
    bank_name = bank.name
    email = mandate.user.email
    sender = bank.support_email
    short_name = bank.short_name
    content = f"Dear {first_name},<br><br>Kindly use the following token to complete transaction. " \
              f"<br><strong>Token: {otp}</strong><br>" \
              f"<br>Regards, <br>{bank_name} Team."
    sms_content = f"Dear {first_name},\nKindly use the following token to complete transaction.\nToken: {otp} \n" \
                  f"Regards,\n{bank_name} Team."
    if short_name in bank_one_banks:
        # Send email
        send_email_to_bankone_mandates(bank, sender, email, subject, content)
        # Send SMS
        send_sms_to_bankone_mandates(bank, account_no, sms_content, receiver)

    return True


def send_successful_transfer_email(mandate, trans_req):
    first_name = mandate.user.first_name
    bank = mandate.institution.bank
    bank_name = bank.name
    subject = "Transaction Processed"
    email = mandate.user.email
    sender = bank.support_email
    short_name = bank.short_name
    content = f"Dear {first_name},<br><br>A transaction has been approved, please see details below: <br>" \
              f"<br><strong>SENT FROM: {trans_req.account_no}</strong>" \
              f"<br><strong>BENEFICIARY NAME: {trans_req.beneficiary_name}</strong>" \
              f"<br><strong>BENEFICIARY ACCOUNT NUMBER: {trans_req.beneficiary_acct}</strong>" \
              f"<br><strong>BENEFICIARY BANK: {trans_req.bank_name}</strong>" \
              f"<br><strong>AMOUNT: {trans_req.amount}</strong>" \
              f"<br><strong>NARRATION: {trans_req.description}</strong><br>" \
              f"<br>Regards, <br>{bank_name} Team."
    if short_name in bank_one_banks:
        send_email_to_bankone_mandates(bank, sender, email, subject, content)
    return True


def send_successful_bill_payment_email(mandate, trans_req):
    first_name = mandate.user.first_name
    bank = mandate.institution.bank
    subject = "Transaction Processed"
    bank_name = bank.name
    email = mandate.user.email
    sender = bank.support_email
    short_name = bank.short_name
    content = f"Dear {first_name},<br><br>A bill payment transaction has been approved, please login to your " \
              f"dashboard to see details <br><br>Regards, <br>{bank_name} Team."
    # f"<br><strong>SENT FROM: {trans_req.account_number}</strong>" \
    # f"<br><strong>BENEFICIARY NAME: {trans_req.beneficiary_name}</strong>" \
    # f"<br><strong>BENEFICIARY ACCOUNT NUMBER: {trans_req.beneficiary_acct}</strong>" \
    # f"<br><strong>BENEFICIARY BANK: {trans_req.bank_name}</strong>" \
    # f"<br><strong>AMOUNT: {trans_req.amount}</strong>" \
    # f"<br><strong>NARRATION: {trans_req.description}</strong><br>" \
    # f"<br>Regards, <br>{bank_name} Team."
    if short_name in bank_one_banks:
        send_email_to_bankone_mandates(bank, sender, email, subject, content)
    return True
