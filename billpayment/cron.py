from threading import Thread

from django.db.models import Q

from bankone.api import send_sms
from billpayment.models import Electricity
from tm_saas.api import retry_electricity


def retry_eko_elect_cron():
    elect = Q(disco_type="EKEDC_PREPAID")
    elect |= Q(disco_type="EKEDC_POSTPAID")
    queryset = Electricity.objects.filter(elect, status="pending").distinct()

    # PERFORM VEND RETRY
    for query in queryset:
        trans_id = query.transaction_id
        response = retry_electricity(trans_id)
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
                    Thread(target=send_sms, args=[query.account_no, content, query.phone_number]).start()
    return "Elect Retry Cron ran successfully"



