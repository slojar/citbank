from django.contrib.auth.models import User
from .models import Customer, CustomerAccount, CustomerOTP
from bankone.api import get_account_by_account_no, get_customer_info_by_customer_id


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
        detail = 'Account is already registered, please proceed to login with your credentials'
        return success, detail

    # API to check if account exist
    response = get_account_by_account_no(account_no)
    if response.status_code == 404:
        detail = str(response.text)
        return success, detail

    customer_data = response.json()

    customer_id = customer_data['CustomerID']
    # account_no = customer_data['NUBAN']

    response = get_customer_info_by_customer_id(customer_id)

    email = response['CustomerDetails']['Email']
    names = str(response['CustomerDetails']['Name']).split(',')

    last_name, first_name = '', ''

    for name in range(len(names)):
        last_name = name[0]
        first_name = name[1].replace(' ', '')

    accounts = response['Accounts']

    # Create User and Customer
    if User.objects.filter(email=email).exists():
        detail = 'Account is already registered, please proceed to login with your credentials'
        return success, detail

    user = User.objects.create(email=email, password=password, last_name=last_name, first_name=first_name)

    customer, created = Customer.objects.get_or_create(user=user)
    customer.customerID = customer_id
    customer.dob = response['CustomerDetails']['DateOfBirth']
    customer.gender = response['CustomerDetails']['Gender']
    customer.phone_number = response['CustomerDetails']['PhoneNumber']
    customer.bvn = response['CustomerDetails']['BVN']
    customer.transaction_pin = transaction_pin
    customer.active = True
    customer.save()

    # Create customer account
    for account in accounts:
        """" Do something """""
        pass

    detail = 'Registration is successful'
    return True, detail




