import decimal
import json
from threading import Thread

from django.conf import settings

from account.models import CustomerAccount
from account.utils import check_account_status, decrypt_text
from bankone.api import bankone_get_details_by_customer_id, bankone_charge_customer, bankone_send_sms, \
    get_corporate_acct_detail
from billpayment.models import Electricity
from tm_saas.api import validate_meter_no, electricity, check_wallet_balance

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


def check_balance_and_charge(user, account_no, amount, ref_code, narration, inst=None):
    # CONFIRM CUSTOMER OWNS THE ACCOUNT
    if user:
        if not CustomerAccount.objects.filter(customer__user=user, active=True, account_no=account_no).exists():
            return False, "Account not found"

        # Check if customer status is active
        customer = CustomerAccount.objects.get(customer__user=user, active=True, account_no=account_no).customer
        check = check_account_status(customer)
        if check is False:
            return False, "Your account is locked, please contact the bank to unlock"

    else:
        customer = inst

    balance_check = check_wallet_balance(customer.bank)
    if "message" in balance_check and balance_check["message"] == "Success":
        balance = balance_check["data"]["balance"]
        # Check if balance is sufficient
        if decimal.Decimal(balance) < decimal.Decimal(amount):
            return False, "An error occurred while vending, please try again later"

    # CHECK ACCOUNT BALANCE
    balance = 0
    token = decrypt_text(customer.bank.auth_token)
    settlement_acct_no = customer.bank.settlement_acct_no
    if inst:
        accounts = get_corporate_acct_detail(customer.customerID, token)
        for account in accounts:
            if account["NUBAN"] == str(account_no):
                balance = str(account["Balance"]["WithdrawableAmount"]).replace(",", "")

    else:
        response = bankone_get_details_by_customer_id(customer.customerID, token).json()
        accounts = response["Accounts"]
        for account in accounts:
            if account["NUBAN"] == str(account_no):
                balance = str(account["withdrawableAmount"]).replace(",", "")

    if float(balance) <= 0:
        return False, "Insufficient balance"

    if float(amount) > float(balance):
        return False, "Amount cannot be greater than current balance"

    # CHARGE CUSTOMER ACCOUNT
    response = bankone_charge_customer(
        account_no=account_no, amount=amount, trans_ref=ref_code, description=narration, auth_token=token,
        settlement_acct=settlement_acct_no
    )
    response = response.json()

    return True, response


def vend_electricity(bank, account_no, disco_type, meter_no, amount, phone_number, ref_code, inst=None):
    token = ""
    response = validate_meter_no(bank, disco_type, meter_no)
    if "error" in response:
        return False, "An error occurred while trying to vend electricity", token

    if disco_type == "IKEDC_POSTPAID":
        data = {
            "disco": "IKEDC_POSTPAID",
            "customerReference": meter_no,
            "customerAddress": response["data"]["address"],
            "amount": amount,
            "customerName": response["data"]["name"],
            "phoneNumber": phone_number,
            "customerAccountType": response["data"]["customerAccountType"],
            "accountNumber": response["data"]["accountNumber"],
            "customerAccountId": meter_no,
            "customerDtNumber": response["data"]["customerDtNumber"],
            "contactType": "LANDLORD"
        }

    elif disco_type == "IKEDC_PREPAID":
        data = {
            "disco": "IKEDC_PREPAID",
            "customerReference": meter_no,
            "customerAccountId": meter_no,
            "canVend": True,
            "customerAddress": response["data"]["address"],
            "meterNumber": meter_no,
            "customerName": response["data"]["name"],
            "customerAccountType": response["data"]["customerAccountType"],
            "accountNumber": response["data"]["accountNumber"],
            "customerDtNumber": response["data"]["customerDtNumber"],
            "amount": amount,
            "phoneNumber": phone_number,
            "contactType": "LANDLORD"
        }

    elif disco_type == "EKEDC_POSTPAID":
        data = {
            "disco": "EKEDC_POSTPAID",
            "accountNumber": meter_no,
            "amount": amount
        }

    elif disco_type == "EKEDC_PREPAID":
        data = {
            "disco": "EKEDC_PREPAID",
            "customerReference": meter_no,
            "canVend": True,
            "customerAddress": response["data"]["customerAddress"],
            "meterNumber": meter_no,
            "customerName": response["data"]["customerName"],
            # "customerDistrict": response["data"]["customerDistrict"],
            "amount": amount
        }

    elif disco_type == "IBEDC_POSTPAID":
        data = {
            "disco": "IBEDC_POSTPAID",
            "customerReference": meter_no,
            "amount": amount,
            "thirdPartyCode": "21",
            "customerName": str(response["data"]["firstName"] + " " + response["data"]["lastName"])
        }

    elif disco_type == "IBEDC_PREPAID":
        data = {
            "disco": "IBEDC_PREPAID",
            "customerReference": meter_no,
            "amount": amount,
            "thirdPartyCode": "21",
            "customerType": "PREPAID",
            "firstName": response["data"]["firstName"],
            "lastName": response["data"]["lastName"]
        }
    else:
        return False, "disco type is not valid", token

    response = electricity(bank, data)
    if "error" in response:
        return False, response["error"], token

    status = "pending"
    transaction_id = response["data"]["transactionId"]
    bill_id = response["data"]["billId"]
    provider_status = response["data"]["providerResponse"]["status"]

    if provider_status == "ACCEPTED":
        status = "success"

    # if response["data"]["providerResponse"]["creditToken"]:

    if response["data"]["providerResponse"]["token"]:
        token = response["data"]["providerResponse"]["token"]

    # Create Electricity Instance
    if inst:
        elect = inst
    else:
        elect = Electricity.objects.create(
            account_no=account_no, disco_type=disco_type, meter_number=meter_no, amount=amount,
            phone_number=phone_number, reference=ref_code, bank=bank
        )
    elect.status = status
    elect.transaction_id = transaction_id
    elect.bill_id = bill_id
    elect.token = token
    elect.save()

    if not token == "":
        # SEND TOKEN TO PHONE NUMBER
        if bank.short_name in bank_one_banks:
            auth_token = decrypt_text(bank.auth_token)
            code = decrypt_text(bank.institution_code)
            content = f"Your {disco_type} token is: {token}".replace("_", " ")
            Thread(target=bankone_send_sms, args=[account_no, content, phone_number, auth_token, code, bank.short_name]).start()
            elect.token_sent = True
            elect.save()

    return True, "vending was successful", token




