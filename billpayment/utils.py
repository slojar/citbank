from threading import Thread

from account.models import CustomerAccount
from bankone.api import get_details_by_customer_id, charge_customer, send_sms
from billpayment.models import Electricity
from tm_saas.api import validate_meter_no, electricity


def check_balance_and_charge(user, account_no, amount, ref_code, narration):
    # CONFIRM CUSTOMER OWNS THE ACCOUNT
    if not CustomerAccount.objects.filter(customer__user=user, active=True, account_no=account_no).exists():
        return False, "Account not found"

    # CHECK ACCOUNT BALANCE
    customer_id = CustomerAccount.objects.get(
        customer__user=user, active=True, account_no=account_no
    ).customer.customerID
    response = get_details_by_customer_id(customer_id).json()

    balance = 0
    accounts = response["Accounts"]
    for account in accounts:
        if account["NUBAN"] == str(account_no):
            balance = str(account["withdrawableAmount"]).replace(",", "")

    if float(balance) <= 0:
        return False, "Insufficient balance"

    if float(amount) > float(balance):
        return False, "Amount cannot be greater than current balance"

    # CHARGE CUSTOMER ACCOUNT
    response = charge_customer(account_no=account_no, amount=amount, trans_ref=ref_code, description=narration)
    response = response.json()

    return True, response


def vend_electricity(account_no, disco_type, meter_no, amount, phone_number, ref_code):
    token = ""
    response = validate_meter_no(disco_type, meter_no)
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
            "customerDistrict": response["data"]["customerDistrict"],
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

    response = electricity(data)
    if "error" in response:
        return False, response["error"], token

    status = "pending"
    transaction_id = response["data"]["transactionId"]
    bill_id = response["data"]["billId"]
    provider_status = response["data"]["providerResponse"]["status"]

    if provider_status == "ACCEPTED":
        status = "success"

    if response["data"]["providerResponse"]["creditToken"]:
        token = response["data"]["providerResponse"]["creditToken"]

    if response["data"]["providerResponse"]["token"]:
        token = response["data"]["providerResponse"]["token"]

    # Create Electricity Instance
    elect = Electricity.objects.create(
        account_no=account_no, disco_type=disco_type, meter_number=meter_no, amount=amount, phone_number=phone_number,
        status=status, transaction_id=transaction_id, bill_id=bill_id, token=token, reference=ref_code
    )

    if not token == "":
        # SEND TOKEN TO PHONE NUMBER
        content = f"Your {disco_type} token is: {token}".replace("_", " ")
        Thread(target=send_sms, args=[account_no, content, phone_number]).start()
        elect.token_sent = True
        elect.save()

    return True, "vending was successful", token




