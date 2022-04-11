import base64
from django.conf import settings
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from .models import Customer, CustomerAccount, CustomerOTP
from bankone.api import get_account_by_account_no
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from cryptography.fernet import Fernet


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

    if not transaction_pin or not password or not transaction_pin_confirm or not password_confirm:
        detail = 'Transaction PIN and Password are required'
        return success, detail

    if len(transaction_pin) != 4:
        detail = 'Transactional PIN can only be 4 digit'
        return success, detail

    if transaction_pin != transaction_pin_confirm:
        detail = 'Transaction PIN mismatch'
        return success, detail

    if password != password_confirm:
        detail = 'Password mismatch'
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

    user = User.objects.create_user(email=email, password=password, last_name=last_name, first_name=first_name, username=email)

    customer, created = Customer.objects.get_or_create(user=user)
    customer.customerID = customer_id
    customer.dob = customer_data['CustomerDetails']['DateOfBirth']
    customer.gender = customer_data['CustomerDetails']['Gender']
    customer.phone_number = customer_data['CustomerDetails']['PhoneNumber']
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
            details, success = "Username and Password are required for login", success
            return details, success

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

        if request.user.is_authenticated:
            details, success = "You are Logged In", True
            return details, success

        details, success = "Details Does not match any Users", success
        return details, success

    except (Exception, ) as err:
        details, success = str(err), False
        return details, success

