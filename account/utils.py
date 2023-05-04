import base64
import calendar
import datetime
import decimal
import json
import logging
import os.path
import random
import uuid
import re
from threading import Thread

from django.conf import settings
from django.contrib.auth import login, authenticate
from django.core.files.base import ContentFile
from django.db.models import Sum, Q

from dateutil.relativedelta import relativedelta

from coporate.models import Institution, TransferRequest
from .models import Customer, CustomerAccount, CustomerOTP, Transaction, AccountRequest

from cryptography.fernet import Fernet

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


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
    if bank.short_name in bank_one_banks:
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
        acct.status = "pending"
        acct.save()

    return True, "Your request is submitted for review. You will get a response soon"


def get_account_balance(customer, customer_type):
    from bankone.api import bankone_get_details_by_customer_id

    data = dict()
    if customer.bank.short_name in bank_one_banks:
        # GET ACCOUNT BALANCES
        token = decrypt_text(customer.bank.auth_token)
        response = bankone_get_details_by_customer_id(customer.customerID, token).json()
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
                account_detail["account_type"] = account["accountType"]
                account_detail["bank_acct_no"] = account["accountNumber"]
                customer_account.append(account_detail)
        data["account_balances"] = customer_account
        Thread(target=update_customer_account, args=[customer, customer_account, customer_type]).start()

    return data


def update_customer_account(customer, account_balances, customer_type):
    for account in account_balances:
        account_no = account["account_no"]
        bank_acct_no = account["bank_acct_no"]
        account_type = account["account_type"]

        if customer_type == "individual":
            if not CustomerAccount.objects.filter(customer=customer, account_no=account_no).exists():
                CustomerAccount.objects.create(
                    customer=customer, account_no=account_no, bank_acct_number=bank_acct_no, account_type=account_type
                )
        else:
            if not CustomerAccount.objects.filter(institution=customer, account_no=account_no).exists():
                CustomerAccount.objects.create(
                    institution=customer, account_no=account_no, bank_acct_number=bank_acct_no, account_type=account_type
                )

    return True


def get_previous_date(date, delta):
    previous_date = date - datetime.timedelta(days=delta)
    return previous_date


def get_next_date(date, delta):
    next_date = date + datetime.timedelta(days=delta)
    return next_date


def get_next_weekday(date, weekday):
    days_ahead = weekday - date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date + datetime.timedelta(days_ahead)


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
    from bankone.api import bankone_transaction_history

    if bank.short_name in bank_one_banks:
        token = decrypt_text(bank.auth_token)
        code = decrypt_text(bank.institution_code)
        response = bankone_transaction_history(
            acct_no=acct_no, page_no=page, date_from=date_from, date_to=date_to, auth_token=token, institution_code=code
        )
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
    from bankone.api import bankone_generate_statement

    if bank.short_name in bank_one_banks:
        # Check if date duration is not more than 6months
        token = decrypt_text(bank.auth_token)
        max_date = get_previous_month_date(datetime.datetime.strptime(date_to, '%Y-%m-%d'), 6)

        if max_date > datetime.datetime.strptime(date_from, '%Y-%m-%d'):
            return False, "The maximum period to generate cannot be greater than six (6) months"

        # Call Bank to generate statement
        response = bankone_generate_statement(
            accountNo=account_no, dateFrom=date_from, dateTo=date_to, format=format_, auth_token=token
        )

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


def get_account_officer(account, bank):
    from bankone.api import bankone_get_customer_acct_officer

    data = dict()
    # bank = account.customer.bank
    if bank.short_name in bank_one_banks:
        account_no = account.account_no
        token = decrypt_text(bank.auth_token)
        # GET ACCOUNT OFFICER
        response = bankone_get_customer_acct_officer(account_no, token)
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
    from bankone.api import bank_flex
    if customer.bvn:
        if customer.bank.short_name in bank_one_banks:
            flex_token = decrypt_text(customer.bank.auth_key_bank_flex)
            bvn = decrypt_text(customer.bvn)
            response = bank_flex(bvn, flex_token)
            if response["code"] != 200:
                return False, "Could not retrieve bank flex details at the moment, please try again later"
            data = response["data"]

            return True, data


def perform_bank_transfer(bank, request):
    from bankone.api import bankone_get_details_by_customer_id, bankone_generate_transaction_ref_code, \
        bankone_local_bank_transfer, bankone_other_bank_transfer

    transfer_type = request.data.get('transfer_type')  # same_bank or other_bank
    account_number = request.data.get('account_no')
    amount = request.data.get('amount')
    description = request.data.get('narration')
    beneficiary_name = request.data.get('beneficiary_name')
    beneficiary_acct = request.data.get('beneficiary_acct_no')
    sender_type = request.data.get('sender_type', 'individual')

    # Needed payloads for other bank transfer
    beneficiary_acct_type = request.data.get("beneficiary_acct_type")  # savings, current, etc
    bank_code = request.data.get("beneficiary_bank_code")
    nip_session_id = request.data.get("nip_session_id")
    bank_name = request.data.get('beneficiary_bank_name')

    transfer_id = request.data.get('transfer_id')

    customer = institution = transfer = trans_req = None
    today_trans = month_transaction = 0
    today = datetime.datetime.today()
    today_date = str(today.date())
    customer_id = sender_name = ""
    today_now = datetime.datetime.now()
    start_date, end_date = get_month_start_and_end_datetime(today_now)

    if sender_type == 'individual':
        if not all([account_number, amount, beneficiary_acct, beneficiary_name]):
            return False, "Required fields are account_number, beneficiary account details, and amount"

        # get the customer the account_number belongs to
        customer_account = CustomerAccount.objects.get(account_no=account_number)
        customer = customer_account.customer
        customer_id = customer.customerID
        sender_name = customer.get_full_name()

        # Check if customer status is active
        result = check_account_status(customer)
        if result is False:
            return False, "Your account is locked, please contact the bank to unlock"

        success, message = confirm_trans_pin(request)
        if success is False:
            return False, message

        # check if account_number is valid
        if not CustomerAccount.objects.filter(account_no=account_number, customer__user=request.user).exists():
            return False, "Account number is not valid"

        # Check Transfer Limit
        if decimal.Decimal(amount) > customer.transfer_limit:
            log_request(f"Amount sent: {decimal.Decimal(amount)}, transfer_limit: {customer.transfer_limit}")
            return False, "amount is greater than your limit. please contact the bank"

        current_limit = float(amount) + float(today_trans)
        today_trans = \
            Transaction.objects.filter(customer=customer, status="success", created_on=today_date).aggregate(
                Sum("amount"))["amount__sum"] or 0

        # Check Daily Transfer Limit
        if current_limit > customer.daily_limit:
            log_request(f"Amount to transfer:{amount}, Total Transferred today: {today_trans}, Exceed: {current_limit}")
            return False, f"Your current daily transfer limit is NGN{customer.daily_limit}, please contact the bank"

        month_transaction = Transaction.objects.filter(created_on__range=(start_date, end_date),
                                                       customer__bank=bank).count()

    if sender_type == 'corporate':
        if transfer_id:
            trans_req = TransferRequest.objects.get(id=transfer_id, approved=True)
            institution = trans_req.institution
        else:
            institution = Institution.objects.get(mandate__user=request.user)
        customer_id = institution.customerID
        sender_name = institution.name

        transfer_type = trans_req.transfer_type  # same_bank or other_bank
        account_number = trans_req.account_no
        amount = trans_req.amount
        description = trans_req.description
        beneficiary_name = trans_req.beneficiary_name
        beneficiary_acct = trans_req.beneficiary_acct
        beneficiary_acct_type = trans_req.beneficiary_acct_type  # savings, current, etc
        bank_code = trans_req.bank_code
        nip_session_id = trans_req.nip_session_id
        bank_name = trans_req.bank_name

        month_transaction = Transaction.objects.filter(created_on__range=(start_date, end_date),
                                                       institution__bank=bank).count()

    # Narration max is 100 char, Reference max is 12 char, amount should be in kobo (i.e multiply by 100)
    narration = ""
    if description:
        narration = description[:100]

    if bank.short_name in bank_one_banks:
        app_zone_acct = ""

        # Compare amount with balance
        balance = 0
        token = decrypt_text(bank.auth_token)
        account = bankone_get_details_by_customer_id(customer_id, token).json()
        for acct in account["Accounts"]:
            if acct["NUBAN"] == account_number:
                withdraw_able = str(acct["withdrawableAmount"]).replace(",", "")
                app_zone_acct = str(acct["accountNumber"])
                balance = decimal.Decimal(withdraw_able)

        if balance <= 0:
            return False, "Insufficient balance"

        if decimal.Decimal(amount) > balance:
            return False, "Amount to transfer cannot be greater than current balance"

        # generate transaction reference using the format CYYMMDDCODES
        code = str(month_transaction + 1)
        ref_code = bankone_generate_transaction_ref_code(code, bank.short_name)

        if transfer_type == "same_bank":
            if not narration:
                narration = "transfer"

            bank_name = bank.name
            response = bankone_local_bank_transfer(
                amount=amount, sender=account_number, receiver=beneficiary_acct, trans_ref=ref_code,
                description=narration, auth_token=token
            )
            # Create Transaction instance
            if sender_type == "individual":
                transfer = Transaction.objects.create(
                    customer=customer, sender_acct_no=account_number, transfer_type="local_transfer",
                    beneficiary_type="local_transfer", beneficiary_name=beneficiary_name, bank_name=bank_name,
                    beneficiary_acct_no=beneficiary_acct, amount=amount, narration=description, reference=ref_code
                )
            if sender_type == "corporate":
                transfer = Transaction.objects.create(
                    institution=institution, sender_acct_no=account_number, transfer_type="local_transfer",
                    beneficiary_type="local_transfer", beneficiary_name=beneficiary_name, bank_name=bank_name,
                    beneficiary_acct_no=beneficiary_acct, amount=amount, narration=description, reference=ref_code,
                    transfer_request=trans_req
                )

            if response["IsSuccessful"] is True and response["ResponseCode"] != "00":
                transfer.status = "failed"
                return False, str(response["ResponseMessage"])

            if response["IsSuccessful"] is False:
                transfer.status = "failed"
                return False, str(response["ResponseMessage"])

            if response["IsSuccessful"] is True and response["ResponseCode"] == "00":
                transfer.status = "success"
            trans_req.response_message = str(response["ResponseMessage"])[:298]
            trans_req.save()
            transfer.save()

        elif transfer_type == "other_bank":
            # Convert kobo amount sent on OtherBankTransfer to naira... To be removed in future update
            # o_amount = amount / 100

            response = bankone_other_bank_transfer(
                amount=amount, bank_acct_no=app_zone_acct, sender_name=sender_name, sender_acct_no=account_number,
                receiver_acct_no=beneficiary_acct, receiver_acct_type=beneficiary_acct_type,
                receiver_bank_code=bank_code, receiver_name=beneficiary_name, auth_token=token,
                description=narration, trans_ref=ref_code,
                nip_session_id=nip_session_id
            )
            # Create transfer
            if sender_type == "individual":
                transfer = Transaction.objects.create(
                    customer=customer, sender_acct_no=account_number, transfer_type="external_transfer",
                    beneficiary_type="external_transfer", beneficiary_name=beneficiary_name, bank_name=bank_name,
                    beneficiary_acct_no=beneficiary_acct, amount=amount, narration=description, reference=ref_code
                )
            if sender_type == "corporate":
                transfer = Transaction.objects.create(
                    institution=institution, sender_acct_no=account_number, transfer_type="external_transfer",
                    beneficiary_type="external_transfer", beneficiary_name=beneficiary_name, bank_name=bank_name,
                    beneficiary_acct_no=beneficiary_acct, amount=amount, narration=description, reference=ref_code,
                    transfer_request=trans_req
                )

            if response["IsSuccessFul"] is True and response["ResponseCode"] != "00":
                transfer.status = "failed"
                return False, str(response["ResponseMessage"])

            if response["IsSuccessFul"] is False:
                transfer.status = "failed"
                return False, str(response["ResponseMessage"])

            if response["IsSuccessFul"] is True and response["ResponseCode"] == "00":
                transfer.status = "success"
            transfer.save()
            trans_req.response_message = str(response["ResponseMessage"])[:298]
            trans_req.save()

        else:
            return False, "Invalid transfer type selected"

    return True, transfer


def perform_name_query(bank, request):
    from bankone.api import bankone_get_account_by_account_no, bankone_others_name_query

    account_no = request.GET.get("account_no")
    bank_code = request.GET.get("bank_code")
    query_type = request.GET.get("query_type")  # same_bank or other_bank

    if not account_no:
        return False, "Account number is required"

    data = dict()
    name = nip_session_id = ""
    bank_one_banks = json.loads(settings.BANK_ONE_BANKS)
    short_name = bank.short_name
    decrypted_token = decrypt_text(bank.auth_token)

    if query_type == "same_bank":
        if short_name in bank_one_banks:
            response = bankone_get_account_by_account_no(account_no, decrypted_token).json()
            if "CustomerDetails" in response:
                customer_detail = response["CustomerDetails"]
                name = customer_detail["Name"]
            else:
                return False, "Could not retrieve account information at the moment"

    elif query_type == "other_bank":

        if not all([account_no, bank_code]):
            return False, "Account number and bank code are required"

        if short_name in bank_one_banks:
            response = bankone_others_name_query(account_no, bank_code, decrypted_token)
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
    from bankone.api import bankone_get_customer_cards

    if not account_no:
        return False, "Account number is required"

    if not CustomerAccount.objects.filter(account_no=account_no, customer=customer).exists():
        return False, "Account number is not valid for authenticated user"

    result = list()

    if customer.bank.short_name in bank_one_banks:
        token = decrypt_text(customer.bank.auth_token)
        response = bankone_get_customer_cards(account_no, token)
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
    from bankone.api import bankone_freeze_or_unfreeze_card

    account_no = request.data.get("account_no")
    reason = request.data.get("reason")
    serial_no = request.data.get("serial_no")
    request_action = request.data.get("action")

    customer = Customer.objects.get(user=request.user)
    if not CustomerAccount.objects.filter(account_no=account_no, customer=customer).exists():
        return False, "Account number is not valid for authenticated user"

    if customer.bank.short_name in bank_one_banks:
        token = decrypt_text(customer.bank.auth_token)
        if not all([serial_no, account_no]):
            return False, "Required: card serial number and account number"
        if request_action == "block":
            action = "freeze"
        elif request_action == "unblock":
            action = "unfreeze"
        else:
            return False, "Invalid action selected. Expected 'block' or 'unblock'"

        response = bankone_freeze_or_unfreeze_card(serial_no, reason, account_no, action, token)
        if response["IsSuccessful"] is False:
            return False, f"Error occurred while {request_action}ing card. Please try again later or contact the bank."

    else:
        return False, "Customer bank not registered. Please try again later or contact the bank."

    return True, f"Card {request_action}ed successfully"


def perform_bvn_validation(bank, bvn):
    from bankone.api import bankone_get_bvn_detail

    success, detail = False, "Error occurred while retrieving BVN information"
    if bank.short_name in bank_one_banks:
        token = decrypt_text(bank.auth_token)
        response = bankone_get_bvn_detail(bvn, token)
        if "RequestStatus" in response:
            if response["RequestStatus"] is True and response["isBvnValid"] is True:
                success, detail = True, response["bvnDetails"]
            else:
                success, detail = False, "Validation error. Please enter correct phone number and BVN"

    return success, detail


def get_fix_deposit_accounts(bank, request):
    from bankone.api import bankone_get_fixed_deposit

    phone_no = request.GET.get("phone_no")

    success = False
    detail = "Error while retrieving fixed account"

    if bank.short_name in bank_one_banks:
        auth_token = decrypt_text(bank.auth_token)
        response = bankone_get_fixed_deposit(phone_no, auth_token)
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
    from bankone.api import generate_random_ref_code, bankone_get_acct_officer, bankone_create_account
    short_name = acct_req.bank.short_name
    if short_name in bank_one_banks:
        token = decrypt_text(acct_req.bank.auth_token)
        prod_code = acct_req.bank.savings_product_code

        # GENERATE TRANSACTION REF
        tran_code = generate_random_ref_code(short_name)

        # GET RANDOM ACCOUNT OFFICER
        officers = bankone_get_acct_officer(token)
        acct_officer = random.choice(officers)
        officer_code = acct_officer["Code"]

        # CONVERT IMAGES TO STRING
        signature_str = base64.b64encode(acct_req.signature.read())
        image_str = base64.b64encode(acct_req.image.read())

        # OPEN ACCOUNT FOR CUSTOMER
        email = str(acct_req.email).replace(" ", "")
        response = bankone_create_account(
            bvnNumber=acct_req.bvn, phoneNumber=acct_req.phone_no, firstName=acct_req.first_name,
            otherName=acct_req.other_name, lastName=acct_req.last_name, gender=acct_req.gender, dob=acct_req.dob,
            nin=acct_req.nin, email=email, address=acct_req.address, transRef=tran_code, product_code=prod_code,
            officerCode=officer_code, signatureString=signature_str, imageString=image_str, auth_token=token
        )

        if response["IsSuccessful"] is False:
            return False, response["Message"]

    return True, "Request submitted for account opening"


def create_or_update_bank(request, bank):
    data = request.data
    short_name = data.get("short_name")
    tm_service_id = data.get("tm_service_id")
    institution_code = data.get("institution_code")
    mfb_code = data.get("mfb_code")
    auth_token = data.get("auth_token")
    auth_key_bank_flex = data.get("auth_key_bank_flex")
    support_email = data.get("support_email")
    enquiry_email = data.get("enquiry_email")
    feedback_email = data.get("feedback_email")
    officer_rating_email = data.get("officer_rating_email")
    registration_email = data.get("registration_email")
    website = data.get("website")
    address = data.get("address")
    bill_payment_charges = data.get("bill_payment_charges")
    tm_notification = data.get("tm_notification")

    if short_name:
        # remove spaces
        s_name = str(short_name).replace(" ", "").lower()
        bank.short_name = s_name
    if support_email:
        bank.support_email = support_email
    if enquiry_email:
        bank.enquiry_email = enquiry_email
    if feedback_email:
        bank.feedback_email = feedback_email
    if officer_rating_email:
        bank.officer_rating_email = officer_rating_email
    if registration_email:
        bank.registration_email = registration_email
    if website:
        bank.website = website
    if address:
        bank.address = address
    if tm_notification:
        bank.tm_notification = tm_notification
    if bill_payment_charges:
        bank.bill_payment_charges = bill_payment_charges
    if tm_service_id:
        bank.tm_service_id = encrypt_text(tm_service_id)
    if auth_token:
        bank.auth_token = encrypt_text(auth_token)
    if institution_code:
        bank.institution_code = encrypt_text(institution_code)
    if mfb_code:
        bank.mfb_code = encrypt_text(mfb_code)
    if auth_key_bank_flex:
        bank.auth_key_bank_flex = encrypt_text(auth_key_bank_flex)
    bank.save()

    return True


def dashboard_transaction_data(bank_id, trans_type):
    trans = dict()
    weekly = []
    monthly = []
    yearly = []
    query = Q(customer__bank_id=bank_id) | Q(institution__bank_id=bank_id)

    if trans_type == "local":
        query &= Q(transfer_type="local_transfer") | Q(transfer_type="transfer")
    elif trans_type == "others":
        query &= Q(transfer_type="external_transfer")

    current_date = datetime.datetime.now()
    for delta in range(6, -1, -1):
        week_total_trans = month_total_trans = year_total_trans = week_count = month_count = year_count = 0
        week_date = current_date - relativedelta(weeks=delta)
        month_date = current_date - relativedelta(months=delta)
        year_date = current_date - relativedelta(years=delta)
        week_start, week_end = get_week_start_and_end_datetime(week_date)
        month_start, month_end = get_month_start_and_end_datetime(month_date)
        year_start, year_end = get_year_start_and_end_datetime(year_date)
        # print(year_start, year_end)
        total_trans = Transaction.objects.filter(query, created_on__range=[week_start, week_end])

        if total_trans:
            week_total_trans = total_trans.aggregate(Sum("amount"))["amount__sum"] or 0
            week_count = total_trans.count()
        weekly.append({"week": f'{week_start.strftime("%d %b")} - {week_end.strftime("%d %b")}',
                       "amount": week_total_trans, "count": week_count})
        total_trans = Transaction.objects.filter(query, created_on__range=[month_start, month_end])

        if total_trans:
            month_total_trans = total_trans.aggregate(Sum("amount"))["amount__sum"] or 0
            month_count = total_trans.count()
        monthly.append({"month": month_start.strftime("%b"), "amount": month_total_trans, "count": month_count})
        total_trans = Transaction.objects.filter(query, created_on__range=[year_start, year_end])
        if total_trans:
            year_total_trans = total_trans.aggregate(Sum("amount"))["amount__sum"] or 0
            year_count = total_trans.count()
        yearly.append({"year": year_start.strftime("%Y"), "amount": year_total_trans, "count": year_count})
    trans['weekly'] = weekly
    trans['monthly'] = monthly
    trans['yearly'] = yearly
    return trans

