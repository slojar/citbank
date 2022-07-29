import base64
import datetime
import uuid
import re

from threading import Thread
from django.conf import settings
from django.contrib.auth import login, authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

from .models import Customer, CustomerAccount, CustomerOTP, Transaction

from bankone.api import get_account_by_account_no, send_sms, send_email

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


def send_otp_message(phone_number, content, subject, account_no, email):
    phone_number = format_phone_number(phone_number)
    success = False
    Thread(target=send_email, args=[email, subject, content]).start()
    # Thread(target=send_email_temporal_fix, args=[email, content, subject]).start()
    response = send_sms(account_no, content, receiver=phone_number)
    # if response['Status'] is False:
    #     detail = 'OTP not sent via sms, please check your email'
    #     return True, detail
    detail = 'OTP successfully sent'

    return True, detail


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


def create_new_customer(data, account_no):
    success = False

    username = data.get('username')
    transaction_pin = data.get('transaction_pin')
    transaction_pin_confirm = data.get('transaction_pin_confirm')
    password = data.get('password')
    password_confirm = data.get('password_confirm')
    token = data.get('otp')

    if not all([username, transaction_pin, password, transaction_pin_confirm, password_confirm, token]):
        detail = 'Username, Transaction PIN, OTP, and Password are required'
        return success, detail

    if len(username) < 8:
        detail = 'Username is too short. Please input minimum of 8 characters'
        return success, detail

    if not (transaction_pin.isnumeric() and len(transaction_pin) == 4):
        detail = 'Transactional PIN can only be 4 digit'
        return success, detail

    if transaction_pin != transaction_pin_confirm:
        detail = 'Transaction PIN mismatch'
        return success, detail

    if password != password_confirm:
        detail = 'Password mismatch'
        return success, detail

    check, detail = validate_password(password)

    if check is False:
        return check, detail

    if User.objects.filter(username=username).exists():
        detail = 'username is taken, please choose another one or contact admin'
        return success, detail

    if CustomerAccount.objects.filter(account_no=account_no).exists():
        detail = 'A profile associated with this account number already exist, please proceed to login or contact admin'
        return success, detail

    try:
        # API to check if account exist
        response = get_account_by_account_no(account_no)
        if response.status_code != 200:
            for response in response.json():
                # print("from for loop: ", response, f"response.json: ", response.json())
                detail = response['error-Message']
                return success, detail

        customer_data = response.json()

        customer_id = customer_data['CustomerDetails']['CustomerID']
        bvn = customer_data['CustomerDetails']['BVN']
        email = customer_data['CustomerDetails']['Email']
        names = str(customer_data['CustomerDetails']['Name']).split(',')
        phone_number = customer_data['CustomerDetails']['PhoneNumber']

        phone_number = format_phone_number(phone_number)

        if token != CustomerOTP.objects.get(phone_number=phone_number).otp:
            detail = 'OTP is not valid'
            return success, detail

        last_name, first_name = '', ''

        for name in range(len(names)):
            last_name = names[0]
            first_name = names[1].replace(' ', '')

        encrypted_bvn = encrypt_text(bvn)
        encrypted_trans_pin = encrypt_text(transaction_pin)

        accounts = customer_data['Accounts']
    except Exception as ex:
        detail = f'An error has occurred: {ex}'
        return success, detail

    # Create User and Customer
    # if User.objects.filter(email=email).exists():
    #     detail = 'Account is already registered, please proceed to login with your credentials'
    #     return success, detail

    user, _ = User.objects.get_or_create(username=username)
    user.password = make_password(password)
    user.email = email
    user.last_name = last_name
    user.first_name = first_name
    user.save()

    customer, created = Customer.objects.get_or_create(user=user)
    customer.customerID = customer_id
    customer.dob = customer_data['CustomerDetails']['DateOfBirth']
    customer.gender = customer_data['CustomerDetails']['Gender']
    customer.phone_number = phone_number
    customer.bvn = encrypted_bvn
    customer.transaction_pin = encrypted_trans_pin
    customer.active = True
    customer.save()

    # Create customer account
    for account in accounts:
        customer_acct, _ = CustomerAccount.objects.get_or_create(customer=customer, account_no=account['NUBAN'])
        customer_acct.account_type = account['AccountType']
        customer_acct.save()

    detail = 'Registration is successful'
    return True, detail


def authenticate_user(request) -> (str, bool):
    try:
        username, password, details, success = request.data.get('username'), request.data.get('password'), '', False

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

    return ref_code


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


def generate_random_ref_code():

    now = datetime.date.today()
    day = str(now.day)
    if len(day) < 2:
        day = f"0{day}"
    month = str(now.month)
    if len(month) < 2:
        month = f"0{month}"
    year = str(now.year)[2:]

    code = str(uuid.uuid4().int)[:5]

    ref_code = f"CIT-{year}{month}{day}{code}"
    return ref_code








