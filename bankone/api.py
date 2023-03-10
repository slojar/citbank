import datetime
import decimal
import json
import uuid
from threading import Thread

import requests
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

from account.models import CustomerAccount, CustomerOTP, Customer, Transaction
from account.utils import decrypt_text

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)

base_url = settings.BANK_ONE_BASE_URL
base_url_3ps = settings.BANK_ONE_3PS_URL
version = settings.BANK_ONE_VERSION
# auth_token = settings.BANK_ONE_AUTH_TOKEN
# institution_code = settings.CIT_INSTITUTION_CODE
# mfb_code = settings.CIT_MFB_CODE
base_url_bank_flex = settings.BANK_FLEX_BASE_URL
# auth_key_bank_flex = settings.BANK_FLEX_KEY


def bankone_get_account_by_account_no(account_no, token):
    from account.utils import log_request
    url = f'{base_url}/Customer/GetByAccountNo/{version}'

    payload = dict()
    payload['authtoken'] = token
    payload['accountNumber'] = account_no

    response = requests.request('GET', url=url, params=payload)
    log_request(url, payload, response.json())
    return response


def bankone_get_details_by_customer_id(customer_id, token):
    from account.utils import log_request
    url = f'{base_url}/Account/GetAccountsByCustomerId/2?authtoken={token}&customerId={customer_id}'

    response = requests.request('GET', url=url)
    log_request(url, response.json())
    return response


def bankone_charge_customer(**kwargs):
    from account.utils import log_request
    url = f"{base_url_3ps}/CoreTransactions/LocalFundsTransfer"

    amount = decimal.Decimal(kwargs.get("amount")) * 100

    payload = dict()
    payload['AuthenticationKey'] = kwargs.get("auth_token")
    payload['Amount'] = amount
    payload['FromAccountNumber'] = kwargs.get("account_no")
    payload['ToAccountNumber'] = kwargs.get("settlement_acct")
    payload['RetrievalReference'] = kwargs.get("trans_ref")
    payload['Narration'] = kwargs.get("description")

    response = requests.request('POST', url=url, data=payload)
    log_request(url, payload, response.json())
    return response


def bankone_log_reversal(tran_date, trans_ref, auth_token):
    from account.utils import log_request
    url = f"{base_url_3ps}/CoreTransactions/Reversal"

    payload = dict()
    payload['Token'] = auth_token
    payload['TransactionType'] = "LOCALFUNDTRANSFER"
    payload['TransactionDate'] = str(tran_date)
    payload['RetrievalReference'] = trans_ref

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def bankone_send_sms(account_no, content, receiver, token, code, bank_code):
    from account.utils import log_request
    url = f'{base_url}/Messaging/SaveBulkSms/{version}?authtoken={token}&institutionCode={code}'
    ref = f'{bank_code}-REF-' + str(uuid.uuid4().int)[:12]

    payload = list()

    data = dict()

    data['AccountNumber'] = account_no
    data['To'] = receiver
    data['AccountId'] = 0
    data['Body'] = content
    data['ReferenceNo'] = ref

    payload.append(data)

    response = requests.request('POST', url=url, json=payload).json()
    log_request(url, payload, response)
    return response


def bankone_send_email(mail_from, to, subject, body, institution_code, mfb_code):
    from account.utils import log_request
    url = f'{base_url}/Messaging/SaveEmail/{version}'

    data = dict()

    data['institutionCode'] = institution_code
    data['mfbCode'] = mfb_code
    data['emailFrom'] = mail_from
    data['emailTo'] = to
    data['subject'] = subject
    data['Message'] = body

    response = requests.request('GET', url, params=data).json()

    log_request(url, data, response)
    return response


def bankone_create_account(**kwargs):
    from account.utils import log_request
    auth_token = kwargs.get("auth_token")
    product_code = kwargs.get("product_code")
    url = f'{base_url}/Account/CreateAccountQuick/{version}?authtoken={auth_token}'
    signature = str(kwargs.get("signatureString"), "utf-8")
    image = str(kwargs.get("imageString"), "utf-8")

    payload = {
        "BVN": kwargs.get("bvnNumber"),
        "PhoneNo": kwargs.get("phoneNumber"),
        "FirstName": kwargs.get("firstName"),
        "OtherNames": kwargs.get("otherName"),
        "LastName": kwargs.get("lastName"),
        "Gender": kwargs.get("gender"),
        "DateOfBirth": kwargs.get("dob"),
        "NIN": kwargs.get("nin"),
        "Email": kwargs.get("email"),
        "Address": kwargs.get("address"),
        "TransactionTrackingRef": kwargs.get("transRef"),
        "ProductCode": product_code,
        "AccountOfficerCode": kwargs.get("officerCode"),
        # select random account officer from acct office ep
        "CustomerSignature": signature,
        "CustomerImage": image,
        "NotificationPreference": 3,
    }

    response = requests.request('POST', url, data=payload).json()
    # sample_response = {'IsSuccessful': True, 'CustomerIDInString': None, 'Message': {'AccountNumber': '1100329130',
    # 'BankoneAccountNumber': '01290031020032913', 'CustomerID': '032913', 'FullName': 'OBADEMI ISAAC',
    # 'CreationMessage': None, 'Id': 236349}, 'TransactionTrackingRef': None, 'Page': None}

    # failed_response = {'IsSuccessful': False, 'CustomerIDInString': None, 'Message': {'AccountNumber': None,
    # 'BankoneAccountNumber': None, 'CustomerID': None, 'FullName': None, 'CreationMessage': 'Invalid Email
    # Address.', 'Id': 0}, 'TransactionTrackingRef': None, 'Page': None}

    log_request(url, payload, response)
    return response


def bankone_get_acct_officer(auth_token):
    from account.utils import log_request
    url = f'{base_url}/AccountOfficer/Get/{version}'

    payload = dict()
    payload['authtoken'] = auth_token

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


def bankone_get_customer_acct_officer(acct_no, auth_token):
    from account.utils import log_request
    url = f'{base_url}/AccountOfficer/GetCustomerAccountOfficer/{version}'

    payload = dict()
    payload['authtoken'] = auth_token
    payload['accountNumber'] = acct_no

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


def bankone_transaction_history(**kwargs):
    from account.utils import log_request
    url = f'{base_url}/Account/GetTransactionsPaginated/{version}'

    page_no = kwargs.get("page_no")
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")
    auth_token = kwargs.get("auth_token")
    institution_code = kwargs.get("institution_code")

    payload = dict()
    payload['authtoken'] = auth_token
    payload['accountNumber'] = kwargs.get("acct_no")
    if date_from and date_to:
        payload['fromDate'] = date_from
        payload['toDate'] = date_to
    payload['institutionCode'] = institution_code
    payload['PageSize'] = 15
    if page_no:
        payload['pageNo'] = page_no
    else:
        payload['pageNo'] = 1

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


def bankone_other_bank_transfer(**kwargs):
    from account.utils import log_request
    url = f'{base_url_3ps}/Transfer/InterBankTransfer'

    amount = decimal.Decimal(kwargs.get("amount")) * 100
    header = {"Content-Type": "application/json"}

    payload = json.dumps(
        {
            "Amount": str(amount),
            "AppzoneAccount": kwargs.get("bank_acct_no"),
            "Payer": kwargs.get("sender_name"),
            "PayerAccountNumber": kwargs.get("sender_acct_no"),
            "ReceiverAccountNumber": kwargs.get("receiver_acct_no"),
            "ReceiverAccountType": kwargs.get("receiver_acct_type"),
            "ReceiverBankCode": kwargs.get("receiver_bank_code"),
            "ReceiverPhoneNumber": "",
            "ReceiverName": kwargs.get("receiver_name"),
            "ReceiverBVN": "",
            "ReceiverKYC": "",
            "Narration": kwargs.get("description"),
            "TransactionReference": kwargs.get("trans_ref"),
            "NIPSessionID": kwargs.get("nip_session_id"),  # this is from NameEnquiry ep
            "Token": kwargs.get("auth_token")
        }
    )

    response = requests.request('POST', url=url, data=payload, headers=header).json()
    log_request(url, payload, response)
    return response


def bankone_others_name_query(account_no, bank_code, auth_token):
    from account.utils import log_request
    url = f'{base_url_3ps}/Transfer/NameEnquiry'

    payload = dict()
    payload['Token'] = auth_token
    payload['BankCode'] = bank_code
    payload['AccountNumber'] = account_no

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def bankone_get_banks(auth_token):
    from account.utils import log_request
    url = f'{base_url_3ps}/BillsPayment/GetCommercialBanks/{auth_token}'

    response = requests.request('GET', url=url).json()
    # log_request(url, response)
    return response


def bankone_get_customer_cards(account_no, auth_token):
    from account.utils import log_request
    url = f'{base_url_3ps}/Cards/RetrieveCustomerCards'

    payload = dict()
    payload['Token'] = auth_token
    payload['AccountNo'] = account_no

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def bankone_freeze_or_unfreeze_card(serial_no, reason, account_no, action, auth_token):
    from account.utils import log_request
    url = ""
    if action == "freeze":
        url = f'{base_url_3ps}/Cards/Freeze'
    if action == "unfreeze":
        url = f'{base_url_3ps}/Cards/UnFreeze'

    payload = dict()
    payload['Token'] = auth_token
    payload['SerialNo'] = serial_no
    payload['Reason'] = reason
    payload['AccountNumber'] = account_no

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def bankone_send_otp_message(phone_number, content, subject, account_no, email, bank):
    from account.utils import format_phone_number
    phone_number = format_phone_number(phone_number)
    if bank.short_name in bank_one_banks:
        email_from = str(bank.support_email)
        token = decrypt_text(bank.auth_token)
        code = decrypt_text(bank.institution_code)
        mfb_code = decrypt_text(bank.mfb_code)
        Thread(target=bankone_send_email, args=[email_from, email, subject, content, code, mfb_code]).start()
        Thread(target=bankone_send_sms, args=[account_no, content, phone_number, token, code, bank.short_name]).start()
    detail = 'OTP successfully sent'

    return True, detail


def bankone_create_new_customer(data, account_no, bank):
    from account.utils import format_phone_number, encrypt_text
    success = False

    username = data.get('username')
    transaction_pin = data.get('transaction_pin')
    transaction_pin_confirm = data.get('transaction_pin_confirm')
    password = data.get('password')
    password_confirm = data.get('password_confirm')
    token = data.get('otp')

    decrypted_token = decrypt_text(bank.auth_token)

    if not all([username, transaction_pin, password, transaction_pin_confirm, password_confirm, token]):
        detail = 'Username, Transaction PIN, OTP, and Password are required'
        return success, detail

    username = str(username).replace(" ", "")

    if len(username) < 8:
        detail = 'Username is too short. Please input minimum of 8 characters'
        return success, detail

    if not (transaction_pin.isnumeric() and len(transaction_pin) == 4):
        detail = 'Transactional PIN can only be 4 digit'
        return success, detail

    if transaction_pin != transaction_pin_confirm:
        detail = 'Transaction PIN mismatch'
        return success, detail

    if not (password.isnumeric() and len(password) == 6):
        detail = 'Password can only be 6 digit'
        return success, detail

    if password != password_confirm:
        detail = 'Password mismatch'
        return success, detail

    # check, detail = validate_password(password)

    # if check is False:
    #     return check, detail

    if User.objects.filter(username=username).exists():
        detail = 'username is taken, please choose another one or contact admin'
        return success, detail

    if CustomerAccount.objects.filter(account_no=account_no).exists():
        detail = 'A profile associated with this account number already exist, please proceed to login or contact admin'
        return success, detail

    try:
        # API to check if account exist
        response = bankone_get_account_by_account_no(account_no, decrypted_token)
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

        # Create User and Customer
        if not email == "" or None:
            if User.objects.filter(email=email).exists():
                detail = 'Account is already registered, please proceed to login with your credentials'
                return success, detail

        user, _ = User.objects.get_or_create(username=username)
        user.password = make_password(password)
        user.email = email
        user.last_name = last_name
        user.first_name = first_name
        user.save()

    except Exception as ex:
        detail = f'An error has occurred: {ex}'
        return success, detail

    customer, created = Customer.objects.get_or_create(user=user)
    customer.bank = bank
    customer.customerID = customer_id
    customer.dob = customer_data['CustomerDetails']['DateOfBirth']
    customer.gender = customer_data['CustomerDetails']['Gender']
    customer.phone_number = phone_number
    customer.bvn = encrypted_bvn
    customer.transaction_pin = encrypted_trans_pin
    customer.save()

    # Create customer account
    for account in accounts:
        customer_acct, _ = CustomerAccount.objects.get_or_create(customer=customer, account_no=account['NUBAN'])
        customer_acct.account_type = account['AccountType']
        customer_acct.bank_acct_number = account['AccountNumber']
        if not account['AccountStatus'] == "Active":
            customer_acct.active = False
        customer_acct.save()

    # send email to admin
    app_reg = str(bank.registration_email)
    sender = str(bank.support_email)
    code = decrypt_text(bank.institution_code)
    mfb_code = decrypt_text(bank.mfb_code)
    content = str("A new customer just registered on the mobile app. Please unlock {f_name} {l_name} with "
                  "username {u_name} and telephone number {tel}.").format(
        f_name=str(user.first_name).title(), l_name=str(user.last_name).title(), u_name=user.username,
        tel=customer.phone_number
    )
    Thread(target=bankone_send_email, args=[sender, app_reg, "New Registration on CIT Mobile App", content, code, mfb_code]).start()

    detail = 'Registration is successful'
    return True, detail


def bankone_generate_transaction_ref_code(code, short_name):
    initial = str(short_name).upper()[0]
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

    ref_code = f"{initial}{year}{month}{day}{code}"
    if Transaction.objects.filter(reference=ref_code).exists():
        x_code = str(uuid.uuid4().int)[:5]
        ref_code = f"{initial}{year}{month}{day}{x_code}"

    return ref_code


def generate_random_ref_code(short_name):
    name = str(short_name).upper()
    now = datetime.date.today()
    day = str(now.day)
    if len(day) < 2:
        day = f"0{day}"
    month = str(now.month)
    if len(month) < 2:
        month = f"0{month}"
    year = str(now.year)[2:]

    code = str(uuid.uuid4().int)[:5]

    ref_code = f"{name}-{year}{month}{day}{code}"
    return ref_code


def bankone_generate_statement(**kwargs):
    from account.utils import log_request
    url = f"{base_url}/Account/GenerateAccountStatement/{version}"

    _format = kwargs.get("format")  # html or pdf

    payload = dict()
    payload['authtoken'] = kwargs.get("auth_token")
    payload['accountNumber'] = kwargs.get("accountNo")
    payload['fromDate'] = kwargs.get("dateFrom")
    payload['toDate'] = kwargs.get("dateTo")
    if _format == "pdf":
        payload['isPdf'] = True
    else:
        payload['isPdf'] = False

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


# Bank Flex API
def bank_flex(bvn, auth_key_bank_flex):
    from account.utils import log_request
    url = f"{base_url_bank_flex}/load_account?bvn={bvn}"
    payload = {}
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {auth_key_bank_flex}'
    }

    response = requests.request("GET", url, headers=headers, data=payload).json()
    log_request(url, headers, response)
    return response


def bankone_local_bank_transfer(**kwargs):
    from account.utils import log_request
    url = f"{base_url_3ps}/CoreTransactions/LocalFundsTransfer"

    amount = decimal.Decimal(kwargs.get("amount")) * 100

    payload = dict()
    payload['AuthenticationKey'] = kwargs.get("auth_token")
    payload['Amount'] = amount
    payload['FromAccountNumber'] = kwargs.get("sender")
    payload['ToAccountNumber'] = kwargs.get("receiver")
    payload['RetrievalReference'] = kwargs.get("trans_ref")
    payload['Narration'] = kwargs.get("description")

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def bankone_get_bvn_detail(bvn, auth_token):
    from account.utils import log_request
    url = f"{base_url_3ps}/Account/BVN/GetBVNDetails"

    payload = dict()
    payload['BVN'] = bvn
    payload['token'] = auth_token

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def bankone_get_fixed_deposit(phone_no, auth_token):
    from account.utils import log_request
    url = f"{base_url}/FixedDeposit/GetFixedDepositAccountByPhoneNumber/{version}"

    payload = dict()
    payload['phoneNumber'] = phone_no
    payload['authtoken'] = auth_token

    response = requests.request('GET', url=url, params=payload)
    print(response.status_code)
    log_request(url, payload, response)
    return response


def bankone_send_statement(request, bank, response):
    name = request.user.first_name
    email = request.data.get("email")
    date_from = request.data.get("date_from")
    date_to = request.data.get("date_to")
    account_no = request.data.get("account_no")

    email_from = str(bank.support_email)
    inst_code = decrypt_text(bank.institution_code)
    mfb_code = decrypt_text(bank.mfb_code)
    message = f"Dear {name},\n" \
              f"Kindly click on the below url to view and/or download your statement\n" \
              f"{response}\n" \
              f"\nThank you for choosing {bank.name}."
    Thread(target=bankone_send_email,
           args=[email_from, email, f"ACCOUNT STATEMENT FROM {date_from} TO {date_to} - {account_no}", message,
                 inst_code, mfb_code]).start()
    result = f"Statement sent to {email}"

    return result



