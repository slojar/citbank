import base64
import uuid
import re

from threading import Thread
from django.conf import settings
from django.contrib.auth import login, authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

from .models import Customer, CustomerAccount, CustomerOTP

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
    response = send_sms(account_no, content, receiver=phone_number)
    if response['Status'] is False:
        detail = 'OTP not sent via sms, please check your email'
        return success, detail
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

    transaction_pin = data.get('transaction_pin')
    transaction_pin_confirm = data.get('transaction_pin_confirm')
    password = data.get('password')
    password_confirm = data.get('password_confirm')
    token = data.get('otp')

    if not transaction_pin or not password or not transaction_pin_confirm or not password_confirm or not token:
        detail = 'Transaction PIN, OTP, and Password are required'
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
    if User.objects.filter(email=email).exists():
        detail = 'Account is already registered, please proceed to login with your credentials'
        return success, detail

    user, _ = User.objects.get_or_create(email=email)
    user.password=make_password(password)
    user.last_name=last_name
    user.first_name=first_name
    user.username=email
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
