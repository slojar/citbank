import json
from account.utils import decrypt_text
from bankone.api import bankone_send_email
from django.conf import settings

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


def send_username_password_to_mandate(mandate, password):
    first_name = mandate.user.first_name
    bank = mandate.institution.bank
    bank_name = bank.name
    short_name = bank.short_name
    sender = bank.support_email
    subject = "Corporate Account (On-boarding)"
    username = mandate.user.username
    email = mandate.user.email
    content = f"Dear {first_name},<br><br>Please find below, your username and password for your corporate account " \
              f"opened at {bank_name}.<br><br>Username: <strong>{username}</strong><br>" \
              f"Password: <strong>{password}</strong><br><br>Kindly change your password upon successful login.<br>" \
              f"<br>Regards, <br>{bank_name} Team."
    if short_name in bank_one_banks:
        inst_code = decrypt_text(bank.institution_code)
        mfb_code = decrypt_text(bank.mfb_code)
        # Send Email
        bankone_send_email(sender, email, subject, content, inst_code, mfb_code)

    return True


