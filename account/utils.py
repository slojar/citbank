import base64
import calendar
import datetime
import decimal
import logging
import os.path
import random
import uuid
import re

from django.conf import settings
from django.contrib.auth import login, authenticate
from django.core.files.base import ContentFile
from django.db.models import Sum

from dateutil.relativedelta import relativedelta

from bankone.api import cit_generate_transaction_ref_code, generate_random_ref_code, cit_get_acct_officer, \
    cit_create_account, \
    cit_get_details_by_customer_id, cit_transaction_history, cit_generate_statement, cit_get_customer_acct_officer, \
    bank_flex, cit_to_cit_bank_transfer, cit_other_bank_transfer, cit_get_account_by_account_no, cit_others_name_query, \
    cit_get_customer_cards, cit_freeze_or_unfreeze_card, cit_get_bvn_detail, cit_get_fixed_deposit
from .models import Customer, CustomerAccount, CustomerOTP, Transaction, AccountRequest

from cryptography.fernet import Fernet


def log_request(*args):
    for arg in args:
        logging.info(arg)


def format_phone_number(phone_number):
    phone_number = f"0{phone_number[-10:]}"
    return phone_number


def generate_new_otp(phone_number):
    otp = str(uuid.uuid4().int)[:6]
    phone_number = format_phone_number(phone_number)
    otp_obj, _ = CustomerOTP.objects.get_or_create(phone_number=phone_number)
    otp_obj.otp = otp
    otp_obj.save()
    return otp


def encrypt_text(text: str):
    key = base64.urlsafe_b64encode(settings.SECRET_KEY.encode()[:32])
    fernet = Fernet(key)
    secure = fernet.encrypt(f"{text}".encode())
    return secure.decode()


def decrypt_text(text: str):
    key = base64.urlsafe_b64encode(settings.SECRET_KEY.encode()[:32])
    fernet = Fernet(key)
    decrypt = fernet.decrypt(text.encode())
    return decrypt.decode()


def authenticate_user(request) -> (str, bool):
    try:
        username, password, details, success = request.data.get('username'), request.data.get('password'), '', False
        username = str(username).replace(" ", "")

        if not (username and password):
            details, success = "username and password are required", success
            return details, success

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

        if request.user.is_authenticated:
            details, success = "Login successful", True
            return details, success

        details, success = "username or password is incorrect", success
        return details, success
    except (Exception,) as err:
        details, success = str(err), False
        return details, success


def validate_password(new_password):
    check, detail = False, ""
    while True:
        if len(new_password) < 8:
            detail = "Password Length must be 8 or above"
            break
        elif not (re.search("[a-z]", new_password)):
            detail = "Password must consist of Lower case"
            break
        elif not (re.search("[A-Z]", new_password)):
            detail = "Password must consist of Upper case"
            break
        elif not (re.search("[0-9]", new_password)):
            detail = "Password must consist of Digits"
            break
        elif not (re.search("[!@#$%_+=?]", new_password)):
            detail = "Password must consist of Special Characters '!@#$%_+=?'"
            break
        elif re.search("\s", new_password):
            detail = "Password should not contain white space"
            break
        else:
            check, detail = True, "Password has been changed successfully"
            break
    return check, detail


def generate_transaction_ref_code(code):
    if len(code) == 1:
        code = f"0000{code}"
    elif len(code) == 2:
        code = f"000{code}"
    elif len(code) == 3:
        code = f"00{code}"
    else:
        code = f"0{code}"

    now = datetime.date.today()
    day = str(now.day)
    if len(day) < 2:
        day = f"0{day}"
    month = str(now.month)
    if len(month) < 2:
        month = f"0{month}"
    year = str(now.year)[2:]

    ref_code = f"C{year}{month}{day}{code}"
    if Transaction.objects.filter(reference=ref_code).exists():
        x_code = str(uuid.uuid4().int)[:5]
        ref_code = f"C{year}{month}{day}{x_code}"

    return ref_code


def check_account_status(customer):
    success = False
    if customer.active is True:
        success = True
    return success


def confirm_trans_pin(request):
    trans_pin = request.data.get('transaction_pin')

    if not trans_pin:
        return False, "Please enter your Transaction PIN"

    customer_pin = Customer.objects.get(user=request.user).transaction_pin
    decrypted_pin = decrypt_text(customer_pin)

    if trans_pin != decrypted_pin:
        return False, "Invalid Transaction PIN"

    return True, "PIN Correct"


def open_account_with_banks(bank, request):
    data = request.data
    if bank.short_name == "cit":
        bvn = data.get("bvn")
        phone = data.get("phone_number")
        f_name = data.get("first_name")
        l_name = data.get("last_name")
        o_name = data.get("other_name")
        gender = data.get("gender")
        dob = data.get("dob")
        nin = data.get("nin")
        email = data.get("email")
        address = data.get("address")
        signature = data.get("signature_image")
        image = data.get("image")
        utility = data.get("utility")
        valid_id = data.get("valid_id")

        if not all([bvn, phone, f_name, l_name, o_name, gender, dob, nin, email, address]):
            return False, "All fields are required to open account with bank"
        if not all([image, signature, utility, valid_id]):
            return False, "Please upload your utility bill, validID, signature and image/picture"
        if not (gender == "male" or gender == "female"):
            return False, "Gender can only be male or female"

        # REFORMAT PHONE NUMBER
        phone_no = format_phone_number(phone)

        # Create Account Opening Request
        acct, _ = AccountRequest.objects.get_or_create(bank=bank, bvn=bvn, email=email)
        acct.bvn = bvn
        acct.phone_no = phone_no
        acct.first_name = f_name
        acct.last_name = l_name
        acct.other_name = o_name
        acct.gender = gender
        acct.dob = dob
        acct.nin = nin
        acct.address = address
        acct.signature = signature
        acct.image = image
        acct.utility = utility
        acct.valid_id = valid_id
        acct.save()

    return True, "Your request is submitted for review. You will get a response soon"


def get_account_balance(customer, request):
    from .serializers import CustomerSerializer

    data = dict()
    if customer.bank.short_name == "cit":
        # GET ACCOUNT BALANCES
        response = cit_get_details_by_customer_id(customer.customerID).json()
        accounts = response["Accounts"]
        customer_account = list()
        for account in accounts:
            account_detail = dict()
            if account["NUBAN"]:
                ledger = str(account["ledgerBalance"]).replace(",", "")
                withdraw_able = str(account["withdrawableAmount"]).replace(",", "")
                available = str(account["availableBalance"]).replace(",", "")

                account_detail["account_no"] = account["NUBAN"]
                account_detail["ledger_balance"] = decimal.Decimal(ledger)
                account_detail["withdrawable_balance"] = decimal.Decimal(withdraw_able)
                account_detail["available_balance"] = decimal.Decimal(available)
                account_detail["kyc_level"] = account["kycLevel"]
                customer_account.append(account_detail)
        print(customer_account)
        data["account_balances"] = customer_account

    data["customer"] = CustomerSerializer(customer, context={"request": request}).data

    return data


def get_previous_date(date, delta):
    previous_date = date - datetime.timedelta(days=delta)
    return previous_date


def get_week_start_and_end_datetime(date_time):
    week_start = date_time - datetime.timedelta(days=date_time.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    week_start = datetime.datetime.combine(week_start.date(), datetime.time.min)
    week_end = datetime.datetime.combine(week_end.date(), datetime.time.max)
    return week_start, week_end


def get_month_start_and_end_datetime(date_time):
    month_start = date_time.replace(day=1)
    month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
    month_start = datetime.datetime.combine(month_start.date(), datetime.time.min)
    month_end = datetime.datetime.combine(month_end.date(), datetime.time.max)
    return month_start, month_end


def get_year_start_and_end_datetime(date_time):
    year_start = date_time.replace(day=1, month=1, year=date_time.year)
    year_end = date_time.replace(day=31, month=12, year=date_time.year)
    year_start = datetime.datetime.combine(year_start.date(), datetime.time.min)
    year_end = datetime.datetime.combine(year_end.date(), datetime.time.max)
    return year_start, year_end


def get_previous_month_date(date, delta):
    return date - relativedelta(months=delta)


def get_transaction_history(bank, acct_no, date_from=None, date_to=None, page=None):
    if bank.short_name == "cit":
        # response = cit_transaction_history(acct_no=acct_no, page_no=page, date_from=date_from, date_to=date_to)
        # BELOW SAMPLE RESPONSE TO BE REMOVED LATER
        response = {
            "IsSuccessful": True,
            "CustomerIDInString": None,
            "Message": {
                "data": [
                    {
                        "Id": 2068633,
                        "CurrentDate": "2022-11-02T15:46:39",
                        "IsReversed": False,
                        "ReversalReferenceNo": None,
                        "WithdrawableAmount": 0.0,
                        "UniqueIdentifier": "C22110200067",
                        "InstrumentNo": "C22110200067",
                        "TransactionDate": "2022-11-01T00:00:00",
                        "TransactionDateString": "Tuesday, November 1, 2022 12:00 AM",
                        "ReferenceID": "A2211010146",
                        "Narration": "tr",
                        "Amount": 500000.0000,
                        "OpeningBalance": 649625.0000,
                        "Balance": 1149625.0000,
                        "PostingType": "ISOPosting",
                        "Debit": "",
                        "Credit": "5,000.00",
                        "IsCardTransation": False,
                        "AccountNumber": None,
                        "ServiceCode": "1007",
                        "RecordType": "Credit"
                    },
                    {
                        "Id": 2068620,
                        "CurrentDate": "2022-11-02T15:27:29",
                        "IsReversed": False,
                        "ReversalReferenceNo": None,
                        "WithdrawableAmount": 0.0,
                        "UniqueIdentifier": "020005951311021527290000000000000000000000",
                        "InstrumentNo": "C22110200066",
                        "TransactionDate": "2022-11-01T00:00:00",
                        "TransactionDateString": "Tuesday, November 1, 2022 12:00 AM",
                        "ReferenceID": "A2211010129",
                        "Narration": "Kilishi",
                        "Amount": 3005575.0000,
                        "OpeningBalance": 3655200.0000,
                        "Balance": 649625.0000,
                        "PostingType": "ISOPosting",
                        "Debit": "30,055.75",
                        "Credit": "",
                        "IsCardTransation": False,
                        "AccountNumber": None,
                        "ServiceCode": "1007",
                        "RecordType": "Debit"
                    },
                    {
                        "Id": 2068550,
                        "CurrentDate": "2022-11-02T14:03:03",
                        "IsReversed": False,
                        "ReversalReferenceNo": None,
                        "WithdrawableAmount": 0.0,
                        "UniqueIdentifier": "020005788611021402580000000000000000000000",
                        "InstrumentNo": "C22110200051",
                        "TransactionDate": "2022-11-01T00:00:00",
                        "TransactionDateString": "Tuesday, November 1, 2022 12:00 AM",
                        "ReferenceID": "A2211010046",
                        "Narration": "Kilishi",
                        "Amount": 1505575.0000,
                        "OpeningBalance": 5160775.0000,
                        "Balance": 3655200.0000,
                        "PostingType": "ISOPosting",
                        "Debit": "15,055.75",
                        "Credit": "",
                        "IsCardTransation": False,
                        "AccountNumber": None,
                        "ServiceCode": "1007",
                        "RecordType": "Debit"
                    }
                ],
                "page": {
                    "size": 3,
                    "totalCount": 20,
                    "totalPages": 7
                }
            },
            "TransactionTrackingRef": None,
            "Page": None
        }
        result = list()
        pages = dict()

        if response["IsSuccessful"] is True:
            messages = response["Message"]["data"]
            paging = response["Message"]["page"]
            pages["size"] = paging["size"]
            pages["item_count"] = paging["totalCount"]
            pages["page_count"] = paging["totalPages"]
            for item in messages:
                message = dict()
                message["date"] = item["TransactionDate"]
                message["date_string"] = item["TransactionDateString"]
                message["direction"] = item["RecordType"]
                message["amount"] = decimal.Decimal(item["Amount"]) / 100
                message["description"] = item["Narration"]
                message["reference_no"] = item["InstrumentNo"]
                result.append(message)

        return result, pages


def generate_bank_statement(request, bank, date_from, date_to, account_no, format_):
    if bank.short_name == "cit":
        # Check if date duration is not more than 6months
        max_date = get_previous_month_date(datetime.datetime.strptime(date_to, '%Y-%m-%d'), 6)

        if max_date > datetime.datetime.strptime(date_from, '%Y-%m-%d'):
            return False, "The maximum period to generate cannot be greater than six (6) months"

        # Call Bank to generate statement
        response = cit_generate_statement(accountNo=account_no, dateFrom=date_from, dateTo=date_to, format=format_)

        statement = ""
        if response["IsSuccessful"] is True:
            statement_string = response["Message"]
            if format_ == "html":
                statement = statement_string
            else:
                save_file = base64.b64decode(statement_string, validate=True)
                content = ContentFile(save_file)
                account = CustomerAccount.objects.get(customer__bank=bank, account_no=account_no)
                account.statement.save(f"statement_{account_no}.pdf", content)
                account.save()

                statement = request.build_absolute_uri(account.statement.url)

        return True, statement


def get_account_officer(account):
    data = dict()
    if account.customer.bank.short_name == "cit":
        account_no = account.account_no
        # GET ACCOUNT OFFICER
        response = cit_get_customer_acct_officer(account_no)
        if response["IsSuccessful"] is True:
            if response["Message"]:
                result = response["Message"]
                data["name"] = result["Name"]
                data["code"] = result["Code"]
                data["gender"] = result["Gender"]
                data["phone_number"] = result["PhoneNumber"]
                data["email"] = result["Email"]
                data["branch"] = result["Branch"]

    return data


def get_bank_flex_balance(customer):
    if customer.bvn:
        # decrypt bvn
        bvn = decrypt_text(customer.bvn)
        response = bank_flex(bvn)
        if response["code"] != 200:
            return False, "Could not retrieve bank flex details at the moment, please try again later"
        data = response["data"]

        return True, data


def perform_bank_transfer(bank, request):
    transfer_type = request.data.get('transfer_type')  # same_bank or other_bank
    account_number = request.data.get('account_no')
    amount = request.data.get('amount')
    description = request.data.get('narration')
    beneficiary_name = request.data.get('beneficiary_name')
    beneficiary_acct = request.data.get('beneficiary_acct_no')

    # Needed payloads for other bank transfer
    beneficiary_acct_type = request.data.get("beneficiary_acct_type")  # savings, current, etc
    bank_code = request.data.get("beneficiary_bank_code")
    nip_session_id = request.data.get("nip_session_id")
    bank_name = request.data.get('beneficiary_bank_name')

    success, message = confirm_trans_pin(request)
    if success is False:
        return False, message

    if not all([account_number, amount, beneficiary_acct, beneficiary_name]):
        return False, "Required fields are account_number, beneficiary account details, and amount"

    # check if account_number is valid
    if not CustomerAccount.objects.filter(account_no=account_number, customer__user=request.user).exists():
        return False, "Account number is not valid"

    # get the customer the account_number belongs to
    customer_account = CustomerAccount.objects.get(account_no=account_number)
    customer = customer_account.customer
    sender_name = customer.get_full_name()

    transfer = None

    if bank.short_name == "cit":
        app_zone_acct = customer_account.bank_acct_number
        # Check Transfer Limit
        if amount > customer.transfer_limit:
            log_request(f"Amount sent: {decimal.Decimal(amount)}, transfer_limit: {customer.transfer_limit}")
            return False, "amount is greater than your limit. please contact the bank"

        # Check Daily Transfer Limit
        today = datetime.datetime.today()
        today_trans = \
            Transaction.objects.filter(customer=customer, status="success", created_on__day=today.day).aggregate(
                Sum("amount"))["amount__sum"] or 0
        current_limit = float(amount) + float(today_trans)
        if current_limit > customer.daily_limit:
            return False, f"Your current daily transfer limit is NGN{customer.daily_limit}, please contact the bank"

        # Check if customer status is active
        result = check_account_status(customer)
        if result is False:
            return False, "Your account is locked, please contact the bank to unlock"

        # Compare amount with customer balance
        balance = 0
        account = cit_get_details_by_customer_id(customer.customerID).json()
        for acct in account["Accounts"]:
            if acct["NUBAN"] == account_number:
                withdraw_able = str(acct["withdrawableAmount"]).replace(",", "")
                balance = decimal.Decimal(withdraw_able)

        if balance <= 0:
            return False, "Insufficient balance"

        if decimal.Decimal(amount) > balance:
            return False, "Amount to transfer cannot be greater than current balance"

        # Narration max is 100 char, Reference max is 12 char, amount should be in kobo (i.e multiply by 100)
        narration = ""
        if description:
            narration = description[:100]
        # generate transaction reference using the format CYYMMDDCODES
        today = datetime.datetime.now()
        start_date, end_date = get_month_start_and_end_datetime(today)
        month_transaction = Transaction.objects.filter(created_on__range=(start_date, end_date)).count()
        code = str(month_transaction + 1)
        ref_code = cit_generate_transaction_ref_code(code)

        if transfer_type == "same_bank":

            bank_name = bank.name
            response = cit_to_cit_bank_transfer(
                amount=amount, sender=account_number, receiver=beneficiary_acct, trans_ref=ref_code,
                description=narration
            )
            # Create Transaction instance
            transfer = Transaction.objects.create(
                customer=customer, sender_acct_no=account_number, transfer_type="local_transfer",
                beneficiary_type="local_transfer", beneficiary_name=beneficiary_name, bank_name=bank_name,
                beneficiary_acct_no=beneficiary_acct, amount=amount, narration=description, reference=ref_code
            )
            if response["IsSuccessful"] is True and response["ResponseCode"] != "00":
                return False, str(response["ResponseMessage"])

            if response["IsSuccessful"] is False:
                return False, str(response["ResponseMessage"])

            if response["IsSuccessful"] is True and response["ResponseCode"] == "00":
                transfer.status = "success"
                transfer.save()

        elif transfer_type == "other_bank":
            # Convert kobo amount sent on OtherBankTransfer to naira... To be removed in future update
            o_amount = amount / 100

            response = cit_other_bank_transfer(
                amount=o_amount, bank_acct_no=app_zone_acct, sender_name=sender_name, sender_acct_no=account_number,
                receiver_acct_no=beneficiary_acct, receiver_acct_type=beneficiary_acct_type,
                receiver_bank_code=bank_code, receiver_name=beneficiary_name,
                description=narration, trans_ref=ref_code,
                nip_session_id=nip_session_id
            )
            # Create transfer
            transfer = Transaction.objects.create(
                customer=customer, sender_acct_no=account_number, transfer_type="external_transfer",
                beneficiary_type="external_transfer", beneficiary_name=beneficiary_name, bank_name=bank_name,
                beneficiary_acct_no=beneficiary_acct, amount=amount, narration=description, reference=ref_code
            )
            if response["IsSuccessFul"] is True and response["ResponseCode"] != "00":
                return False, str(response["ResponseMessage"])

            if response["IsSuccessFul"] is False:
                return False, str(response["ResponseMessage"])

            if response["IsSuccessFul"] is True and response["ResponseCode"] == "00":
                transfer.status = "success"
                transfer.save()

        else:
            return False, "Invalid transfer type selected"

    return True, transfer


# <<<<<<< HEAD
    # generate transaction reference using the format CYYMMDDCODES
    # now = datetime.datetime.now()
    # start_date = now.date()
    # start_date = datetime.datetime.today().date().replace(day=1)
    # end_date = datetime.date(now.year, 1 if now.month == 12 else now.month + 1, 1) - datetime.timedelta(days=1)
    # month_transaction = Transaction.objects.filter(created_on__range=(start_date, end_date)).count()
    # code = str(month_transaction + 1)
    # ref_code = generate_transaction_ref_code(code)
# =======
def perform_name_query(bank, request):
# >>>>>>> 6c352fec3d64e2f59105de1e67a931b2519194b4

    account_no = request.GET.get("account_no")
    bank_code = request.GET.get("bank_code")
    query_type = request.GET.get("query_type")  # same_bank or other_bank

    if not account_no:
        return False, "Account number is required"

    data = dict()
    name = nip_session_id = ""

    if query_type == "same_bank":
        if bank.short_name == "cit":
            response = cit_get_account_by_account_no(account_no).json()
            if "CustomerDetails" in response:
                customer_detail = response["CustomerDetails"]
                name = customer_detail["Name"]
            else:
                return False, "Could not retrieve account information at the moment"

    elif query_type == "other_bank":

        if not all([account_no, bank_code]):
            return False, "Account number and bank code are required"

        if bank.short_name == "cit":
            response = cit_others_name_query(account_no, bank_code)
            if response["IsSuccessful"] is True:
                name = response["Name"]
                nip_session_id = response["SessionID"]

    else:
        return False, "You have selected a wrong query type"

    data["name"] = name
    data["nip_session_id"] = nip_session_id

    return True, data


def retrieve_customer_card(customer, account_no):
    # function is expected to return card number, expiry date, name on card, and/or serial number (optional)
    # card_no = expiry_date = serial_no = name = ""

    if not account_no:
        return False, "Account number is required"

    if not CustomerAccount.objects.filter(account_no=account_no, customer=customer).exists():
        return False, "Account number is not valid for authenticated user"

    result = list()

    if customer.bank.short_name == "cit":
        response = cit_get_customer_cards(account_no)
        if response["isSuccessful"] is True:
            cards = response["Cards"]
            data = dict()
            for card in cards:
                data["card_no"] = card["CardPAN"]
                data["expiry_date"] = card["ExpiryDate"]
                data["serial_no"] = card["SerialNo"]
                data["name"] = card["NameOnCard"]
                data["status"] = card["Status"]
                data["account_no"] = card["AccountNumber"]
                result.append(data)

    return True, result


def block_or_unblock_card(request):
    account_no = request.data.get("account_no")
    reason = request.data.get("reason")
    serial_no = request.data.get("serial_no")
    request_action = request.data.get("action")

    customer = Customer.objects.get(user=request.user)
    if not CustomerAccount.objects.filter(account_no=account_no, customer=customer).exists():
        return False, "Account number is not valid for authenticated user"

    if customer.bank.short_name == "cit":
        if not all([serial_no, account_no]):
            return False, "Required: card serial number and account number"
        if request_action == "block":
            action = "freeze"
        elif request_action == "unblock":
            action = "unfreeze"
        else:
            return False, "Invalid action selected. Expected 'block' or 'unblock'"

        response = cit_freeze_or_unfreeze_card(serial_no, reason, account_no, action)
        if response["IsSuccessful"] is False:
            return False, f"Error occurred while {request_action}ing card. Please try again later or contact the bank."

    else:
        return False, "Customer bank not registered. Please try again later or contact the bank."

    return True, f"Card {request_action}ed successfully"


def perform_bvn_validation(bank, bvn):
    success, detail = False, "Error occurred while retrieving BVN information"
    if bank.short_name == "cit":
        response = cit_get_bvn_detail(bvn)
        if "RequestStatus" in response:
            if response["RequestStatus"] is True and response["isBvnValid"] is True:
                success, detail = True, response["bvnDetails"]
            else:
                success, detail = False, response["ResponseMessage"]

    return success, detail


def get_fix_deposit_accounts(bank, request):
    phone_no = request.GET.get("phone_no")

    success = False
    detail = "Error while retrieving fixed account"

    if bank.short_name == "cit":
        response = cit_get_fixed_deposit(phone_no)
        if response.status_code == 404:
            detail = response.json()
        if response.status_code == 200:
            result = response.json()
            detail = list()
            for item in result:
                data = dict()
                data["amount"] = item["Amount"]
                data["interest"] = item["interestRate"]
                data["maturity_date"] = item["MaturationDate"]
                data["status"] = item["AccountStatus"]
                data["tenure"] = item["TenureInDays"]
                data["commencement_date"] = item["InterestAccrualCommencementDate"]
                detail.append(data)
            success = True

    return success, detail


def review_account_request(acct_req):
    if acct_req.bank.short_name == "cit":

        # GENERATE TRANSACTION REF
        tran_code = generate_random_ref_code()

        # GET RANDOM ACCOUNT OFFICER
        officers = cit_get_acct_officer()
        acct_officer = random.choice(officers)
        officer_code = acct_officer["Code"]

        # CONVERT IMAGES TO STRING
        signature_str = base64.b64encode(acct_req.signature.read())
        image_str = base64.b64encode(acct_req.image.read())

        # OPEN ACCOUNT FOR CUSTOMER
        response = cit_create_account(
            bvnNumber=acct_req.bvn, phoneNumber=acct_req.phone_no, firstName=acct_req.first_name,
            otherName=acct_req.other_name, lastName=acct_req.last_name, gender=acct_req.gender, dob=acct_req.dob,
            nin=acct_req.nin, email=acct_req.email, address=acct_req.address, transRef=tran_code,
            officerCode=officer_code, signatureString=signature_str, imageString=image_str
        )

        if response["IsSuccessful"] is False:
            return False, response["Message"]["CreationMessage"]
        return True, "Request submitted for account opening"







