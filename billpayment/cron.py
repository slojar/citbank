import datetime
import json
from threading import Thread

from django.conf import settings
from django.db.models import Q, Sum

from account.models import Bank, Transaction
from account.utils import decrypt_text, payattitude_outbound_transfer
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
                    Thread(target=bankone_send_sms, args=[query.account_no, content, query.phone_number, auth_token, code, bank.short_name]).start()
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
                notify = json.dumps(bank.tm_notification).replace(" ", "").replace('"', '').split(",")
                inst_code = decrypt_text(bank.institution_code)
                mfb_code = decrypt_text(bank.mfb_code)
                response = check_wallet_balance(bank)
                subject = "Bills Payment Account Balance"
                sender = "tmsaas@tm30.net"
                if "message" in response and response["message"] == "Success":
                    balance = response["data"]["balance"]
                    content = f"Kindly note that your UBalance is below the required threshold. Your balance is N{balance}"
                    # Check if balance is below 50000
                    if balance < 50000:
                        # Send email to bank and TM SaaS Admins
                        for email in notify:
                            Thread(target=bankone_send_email, args=[sender, email, subject, content, inst_code, mfb_code]).start()

    return "Bill Payment Balance Check Cron ran successfully"


def perform_payattitude_settlement_cron():
    # Get all previous day transactions
    pos_charge = float(settings.PAYATTITUDE_SETTLEMENT_POS_CHARGE)
    web_charge = float(settings.PAYATTITUDE_SETTLEMENT_WEB_CHARGE)
    atm_one_charge = float(settings.PAYATTITUDE_SETTLEMENT_ATM_CHARGE_ONE)
    atm_two_charge = float(settings.PAYATTITUDE_SETTLEMENT_ATM_CHARGE_TWO)
    current_date = datetime.datetime.now()
    yesterday = current_date - datetime.timedelta(days=1)
    transactions = Transaction.objects.filter(
        created_on__gte=yesterday.date(), created_on__lte=yesterday.date(), status="success",
        transfer_type="payattitude"
    )
    # Get and sum-up all pos fee
    total_pos_fee = transactions.filter(channel="pos").aggregate(Sum("fee"))["fee__sum"] or 0
    pos_percent = float(total_pos_fee * pos_charge)
    pos_commission_to_send = total_pos_fee - pos_percent
    # Get and sum-up all web fee
    total_web_fee = transactions.filter(channel="web").aggregate(Sum("fee"))["fee__sum"] or 0
    web_percent = float(total_web_fee * web_charge)
    web_commission_to_send = total_web_fee - web_percent
    # Get and sum-up all atm fee
    total_atm = transactions.filter(channel="atm")
    atm_commission_to_send = 0
    for item in total_atm:
        fee_charged = item.fee
        commission = atm_one_charge
        if item.amount > 5000:
            commission = atm_two_charge
        # Subtract commission from fee
        commission_to_send = fee_charged - commission
        atm_commission_to_send += commission_to_send

    total_commission_to_send = pos_commission_to_send + web_commission_to_send + atm_commission_to_send

    # Send commission to payattitude
    payattitude_outbound_transfer(total_commission_to_send, yesterday.date())
    return "Payattitude Settlement Ran Successfully"


