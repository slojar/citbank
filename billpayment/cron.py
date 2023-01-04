from threading import Thread

from django.db.models import Q

from account.utils import decrypt_text
from bankone.api import bankone_send_sms, bankone_log_reversal
from billpayment.models import Electricity, BillPaymentReversal
from tm_saas.api import retry_electricity


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


