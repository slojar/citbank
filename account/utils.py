import base64
import datetime
import decimal
import uuid
import re

from django.conf import settings
from django.contrib.auth import login, authenticate
from django.db.models import Sum

from bankone.api import generate_transaction_ref_code, generate_random_ref_code, get_acct_officer
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
        phone_no = data.get("phone_no")
        fname = data.get("first_name")
        lname = data.get("last_name")
        oname = data.get("other_name")
        gender = data.get("gender")
        dob = data.get("dob")
        nin = data.get("nin")
        email = data.get("email")
        address = data.get("address")
        signature = data.get("signature_image")
        image = data.get("image")

        if not all([bvn, phone_no, fname, lname, oname, gender, dob, nin, email, address]):
            return False, "All fields are required to open account with bank"
        if not all([image, signature]):
            return False, "Please upload your signature and image/picture"

        # GENERATE TRANSACTION REF
        code = generate_random_ref_code()

        # GET RANDOM ACCOUNT OFFICER
        acct_officer = get_acct_officer()
    return True, "Account opening was successful"




