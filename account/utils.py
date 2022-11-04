import base64
import calendar
import datetime
import decimal
import os.path
import random
import uuid
import re

from django.conf import settings
from django.contrib.auth import login, authenticate
from django.core.files.base import ContentFile
from django.db.models import Sum

from dateutil.relativedelta import relativedelta

from bankone.api import generate_transaction_ref_code, generate_random_ref_code, get_acct_officer, cit_create_account, \
    cit_get_details_by_customer_id, cit_transaction_history, cit_generate_statement
from .models import Customer, CustomerAccount, CustomerOTP, Transaction

from cryptography.fernet import Fernet


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
        from bankone.api import log_request
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
        officers = get_acct_officer()
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

        # The below sample response to be removed
        # response = {
        #     "IsSuccessful": True,
        #     "CustomerIDInString": None,
        #     "Message": "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NzcgNzIyIDY2NiA2MTAgNzIyIDY2NiA5NDMgMCA2NjYgMCAwIDAgMCAwIDAgMCA1NTYgNTU2IDUwMCA1NTYgNTU2IDI3NyA1NTYgNTU2IDIyMiAwIDUwMCAyMjIgODMzIDU1NiA1NTYgNTU2IDU1NiAzMzMgNTAwIDI3NyA1NTYgNTAwIDcyMiAwIDUwMF0vRm9udERlc2NyaXB0b3IgMTYgMCBSPj4KZW5kb2JqCjMgMCBvYmoKPDwvVHlwZS9Gb250L1N1YnR5cGUvVHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhL0VuY29kaW5nL1dpbkFuc2lFbmNvZGluZz4+CmVuZG9iago3IDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgNS9LaWRzWzEgMCBSIDkgMCBSIDExIDAgUiAxMyAwIFIgMTUgMCBSXS9JVFhUKDUuMS4xKT4+CmVuZG9iagoxNyAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgNyAwIFIvUGFnZUxheW91dC9TaW5nbGVQYWdlL09wZW5BY3Rpb248PC9TL0dvVG8vRFsxIDAgUi9GaXRCViAwLjhdPj4+PgplbmRvYmoKMTggMCBvYmoKPDwvUHJvZHVjZXIoaVRleHRTaGFycCA1LjEuMSBcKGNcKSAxVDNYVCBCVkJBKS9DcmVhdGlvbkRhdGUoRDoyMDIyMTEwMzIxMTI1OSswMScwMCcpL01vZERhdGUoRDoyMDIyMTEwMzIxMTI1OSswMScwMCcpPj4KZW5kb2JqCnhyZWYKMCAxOQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDgyMTQgMDAwMDAgbiAKMDAwMDAyMjIxNSAwMDAwMCBuIAowMDAwMDIyNjc1IDAwMDAwIG4gCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwNTI5MCAwMDAwMCBuIAowMDAwMDA3Mzc0IDAwMDAwIG4gCjAwMDAwMjI3NjMgMDAwMDAgbiAKMDAwMDAwODQyNCAwMDAwMCBuIAowMDAwMDEyNDEyIDAwMDAwIG4gCjAwMDAwMTI1NzkgMDAwMDAgbiAKMDAwMDAxNjQ0MyAwMDAwMCBuIAowMDAwMDE2NjEyIDAwMDAwIG4gCjAwMDAwMjA1NTAgMDAwMDAgbiAKMDAwMDAyMDcxOSAwMDAwMCBuIAowMDAwMDIxODg4IDAwMDAwIG4gCjAwMDAwMjIwNTcgMDAwMDAgbiAKMDAwMDAyMjg1MyAwMDAwMCBuIAowMDAwMDIyOTYyIDAwMDAwIG4gCnRyYWlsZXIKPDwvU2l6ZSAxOS9Sb290IDE3IDAgUi9JbmZvIDE4IDAgUi9JRCBbPDJlMDQxZDU1MDAwNWMxYWM0ODdjOTg3OGUxZjc0MDUyPjxlN2YwY2E2MGEwNzg5MTBjMDRiMmEzZjUxMmNkMzUyNj5dPj4Kc3RhcnR4cmVmCjIzMDk4CiUlRU9GCg==",
        #     "TransactionTrackingRef": None,
        #     "Page": None
        # }
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






