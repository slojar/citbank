import json
from threading import Thread

from django.conf import settings
from django.db.models import Q

from account.models import Bank
from account.utils import decrypt_text
from bankone.api import bankone_send_sms, bankone_log_reversal, bankone_send_email
from billpayment.models import Electricity, BillPaymentReversal
from tm_saas.api import retry_electricity, check_wallet_balance

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


def retry_eko_elect_cron():
    elect = Q(disco_type="EKEDC_PREPAID")
    elect |= Q(disco_type="EKEDC_POSTPAID")
    queryset = Electricity.objects.filter(elect, status="pending").distinct()

    # PERFORM VEND RETRY
    for query in queryset:
        trans_id = query.transaction_id
        bank = query.bank
        auth_token = decrypt_text(bank.auth_token)
        code = decrypt_text(bank.institution_code)
        response = retry_electricity(bank, trans_id)
        if response["data"]:
            if response["data"]["status"]:
                if response["data"]["status"] == "ACCEPTED":
                    token = response["data"]["standardTokenValue"]
                    # UPDATE QUERY
                    query.status = "success"
                    query.token = token
                    query.save()
                    # SEND TOKEN
                    content = f"Your EKEDC PREPAID token is: {token}"
                    Thread(target=bankone_send_sms, args=[query.account_no, content, query.phone_number, auth_token, code]).start()
    return "Elect Retry Cron ran successfully"


def bill_payment_reversal_cron():
    queryset = BillPaymentReversal.objects.filter(status="pending")

    for query in queryset:
        trans_date = query.transaction_date
        trans_ref = query.transaction_reference
        auth_token = decrypt_text(query.bank.auth_token)
        response = bankone_log_reversal(trans_date, trans_ref, auth_token)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":
            ref_no = response["Reference"]
            query.status = "completed"
            query.ref = ref_no
            query.save()

    return "Bill Payment Reversal Cron ran successfully"


def check_tm_saas_wallet_balance_cron():
    bank_one = Bank.objects.filter(short_name__in=bank_one_banks)
    if bank_one:
        for bank in bank_one:
            if bank.tm_service_id and bank.tm_notification:
                notify = json.dumps(str(bank.tm_notification).replace(" ", "").split(","))
                inst_code = decrypt_text(bank.institution_code)
                mfb_code = decrypt_text(bank.mfb_code)
                response = check_wallet_balance(bank)
                response = {
                    'message': 'Success',
                    'data': {
                        'balance': 5777.26,
                        'overDraftAmount': 0,
                        'clientId': 'local_d2dddefdafe389d27f64',
                        'userId': '61e5539f00329baec50d9c4d'
                    }
                }
                subject = "Bills Payment Account Balance"
                sender = "tmsaas@tm30.net"
                if "message" in response and response["message"] == "Success":
                    balance = response["data"]["balance"]
                    content = f"Kindly note that your UBalance is below the required threshold. Your balance is N{balance}"
                    # Check if balance is below 50000
                    if balance < 50000:
                        # Send email to bank and TM SaaS Admins
                        for email in notify:
                            Thread(target=bankone_send_email, args=[sender, email, content, inst_code, mfb_code]).start()

    return "Bill Payment Balance Check Cron ran successfully"

