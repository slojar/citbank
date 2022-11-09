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

from bankone.api import generate_transaction_ref_code, generate_random_ref_code, cit_get_acct_officer, \
    cit_create_account, \
    cit_get_details_by_customer_id, cit_transaction_history, cit_generate_statement, cit_get_customer_acct_officer, \
    bank_flex
from .models import Customer, CustomerAccount, CustomerOTP, Transaction

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


def check_account_status(customer):
    success = False
    if customer.active is True:
        success = True
    return success


def create_transaction(request):
    data = request.data

    account_number = data.get('account_number')
    trans_type = data.get('transaction_type')
    trans_option = data.get('transaction_option')
    amount = data.get('amount')
    narration = data.get('narration')
    beneficiary_name = data.get('beneficiary_name', '')
    biller_name = data.get('biller_name', '')
    beneficiary_number = data.get('beneficiary_number', '')

    # ensure all input are received
    if not (account_number and trans_type and trans_option and account_number and amount and narration):
        return False, "required fields are account_number, transaction_type, transaction_option, amount and narration"

    # check if account_number is valid
    if not CustomerAccount.objects.filter(account_no=account_number).exists():
        return False, "account number is not valid"

    # get the customer the account_number belongs to
    customer = CustomerAccount.objects.filter(account_no=account_number).first().customer

    # convert amount from to NGN
    amount = decimal.Decimal(amount) / 100

    # Check Transfer Limit
    if amount > customer.transfer_limit:
        log_request(f"Amount sent: {decimal.Decimal(amount)}, transfer_limit: {customer.transfer_limit}")
        return False, "amount is greater than your limit. please contact the bank"

    # Check Daily Transfer Limit
    today = datetime.datetime.today()
    today_trans = Transaction.objects.filter(customer=customer, status="success", created_on__day=today.day).aggregate(Sum("amount"))["amount__sum"] or 0
    current_limit = float(amount) + float(today_trans)
    if current_limit > customer.daily_limit:
        return False, f"Your current daily transfer limit is NGN{customer.daily_limit}, please contact the bank"

    # Check if customer status is active
    result = check_account_status(customer)
    if result is False:
        return False, "Your account is locked, please contact the bank to unlock"

    # generate transaction reference using the format CYYMMDDCODES
    now = datetime.datetime.now()
    start_date = now.date()
    end_date = datetime.date(now.year, 1 if now.month == 12 else now.month + 1, 1) - datetime.timedelta(days=1)
    month_transaction = Transaction.objects.filter(created_on__range=(start_date, end_date)).count()
    code = str(month_transaction + 1)
    ref_code = generate_transaction_ref_code(code)

    transaction = Transaction.objects.create(customer=customer, transaction_type=trans_type, narration=narration,
                                             transaction_option=trans_option, amount=amount, reference=ref_code,
                                             beneficiary_name=beneficiary_name, biller_name=biller_name,
                                             beneficiary_number=beneficiary_number)
    return True, transaction.reference


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

        if not all([bvn, phone, f_name, l_name, o_name, gender, dob, nin, email, address]):
            return False, "All fields are required to open account with bank"
        if not all([image, signature]):
            return False, "Please upload your signature and image/picture"

        # REFORMAT PHONE NUMBER
        phone_no = format_phone_number(phone)

        # GENERATE TRANSACTION REF
        tran_code = generate_random_ref_code()

        # GET RANDOM ACCOUNT OFFICER
        officers = cit_get_acct_officer()
        acct_officer = random.choice(officers)
        officer_code = acct_officer["Code"]

        # CONVERT IMAGES TO STRING
        signature_str = base64.b64encode(signature.read())
        image_str = base64.b64encode(image.read())

        # OPEN ACCOUNT FOR CUSTOMER
        response = cit_create_account(
            bvnNumber=bvn, phoneNumber=phone_no, firstName=f_name, otherName=o_name, lastName=l_name, gender=gender,
            dob=dob, nin=nin, email=email, address=address, transRef=tran_code, officerCode=officer_code,
            signatureString=signature_str, imageString=image_str
        )

        if response["IsSuccessful"] is False:
            return False, response["Message"]["CreationMessage"]

    return True, "Account opening was successful"


def get_account_balance(customer, request):
    from .serializers import CustomerSerializer

    data = dict()
    if customer.bank.short_name == "cit":
        # GET ACCOUNT BALANCES
        response = cit_get_details_by_customer_id(customer.customerID).json()
        accounts = response["Accounts"]
        customer_account = list()
        for account in accounts:
            if account["NUBAN"]:
                account_detail = dict()
                account_detail["account_no"] = account["NUBAN"]
                account_detail["ledger_balance"] = decimal.Decimal(account["ledgerBalance"]) / 100
                account_detail["withdrawable_balance"] = decimal.Decimal(account["withdrawableAmount"]) / 100
                account_detail["kyc_level"] = account["kycLevel"]
                account_detail["available_balance"] = decimal.Decimal(account["availableBalance"]) / 100
                customer_account.append(account_detail)
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





