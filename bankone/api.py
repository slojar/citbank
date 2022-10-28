import json
import time
import uuid

import requests
import logging
from django.conf import settings

base_url = settings.BANK_ONE_BASE_URL
base_url_3ps = settings.BANK_ONE_3PS_URL
version = settings.BANK_ONE_VERSION
auth_token = settings.BANK_ONE_AUTH_TOKEN
institution_code = settings.CIT_INSTITUTION_CODE
mfb_code = settings.CIT_MFB_CODE
email_from = settings.CIT_EMAIL_FROM


def log_request(*args):
    for arg in args:
        logging.info(arg)


def get_account_by_account_no(account_no):
    url = f'{base_url}/Customer/GetByAccountNo/{version}'

    payload = dict()
    payload['authtoken'] = auth_token
    payload['accountNumber'] = account_no

    response = requests.request('GET', url=url, params=payload)
    log_request(url, payload, response.json())
    return response


def get_details_by_customer_id(customer_id):
    url = f'{base_url}/Account/GetAccountsByCustomerId/2?authtoken={auth_token}&customerId={customer_id}'

    response = requests.request('GET', url=url)
    log_request(url, response.json())
    return response


def charge_customer(**kwargs):
    url = f"{base_url_3ps}/CoreTransactions/LocalFundsTransfer"

    amount = kwargs.get("amount") * 100

    payload = dict()
    payload['AuthenticationKey'] = auth_token
    payload['Amount'] = amount
    payload['FromAccountNumber'] = kwargs.get("account_no")
    payload['ToAccountNumber'] = 1100303086
    payload['RetrievalReference'] = kwargs.get("trans_ref")
    payload['Narration'] = kwargs.get("description")

    response = requests.request('POST', url=url, data=payload)
    log_request(url, payload, response.json())
    return response


def log_reversal(tran_date, trans_ref):
    url = f"{base_url_3ps}/CoreTransactions/Reversal"

    payload = dict()
    payload['Token'] = auth_token
    payload['TransactionType'] = "LOCALFUNDTRANSFER"
    payload['TransactionDate'] = str(tran_date)
    payload['RetrievalReference'] = trans_ref

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def send_sms(account_no, content, receiver):
    url = f'{base_url}/Messaging/SaveBulkSms/{version}?authtoken={auth_token}&institutionCode={institution_code}'
    ref = 'CIT-REF-' + str(uuid.uuid4().int)[:12]

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


def send_email(to, subject, body):
    url = f'{base_url}/Messaging/SaveEmail/{version}'

    data = dict()

    data['institutionCode'] = institution_code
    data['mfbCode'] = mfb_code
    data['emailFrom'] = email_from
    data['emailTo'] = to
    data['subject'] = subject
    data['Message'] = body

    response = requests.request('GET', url, params=data).json()

    log_request(url, data, response)
    return response


def send_enquiry_email(mail_from, email_to, subject, body):
    url = f'{base_url}/Messaging/SaveEmail/{version}'

    data = dict()

    data['institutionCode'] = institution_code
    data['mfbCode'] = mfb_code
    data['emailFrom'] = mail_from
    data['emailTo'] = email_to
    data['subject'] = subject
    data['Message'] = body

    response = requests.request('GET', url, params=data).json()

    log_request(url, data, response)
    return response


def create_account(**kwargs):
    url = f'{base_url}/Account/CreateAccountQuick/{version}?{auth_token}'

    payload = json.dumps({
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
        "ProductCode": 102,
        "AccountOfficerCode": kwargs.get("officeCode"),
        # select random account officer from acct office ep
        "CustomerSignature": kwargs.get("signatureString"),
        "CustomerImage": kwargs.get("imageString"),
        "NotificationPreference": 3,
    })

    response = requests.request('POST', url, data=payload).json()

    log_request(url, payload, response)
    return response


def get_acct_officer():
    url = f'{base_url}/AccountOfficer/Get/{version}'

    payload = dict()
    payload['authtoken'] = auth_token

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


def get_fix_deposit_by_phone_no(phone_no):
    url = f'{base_url}/FixedDeposit/GetFixedDepositAccountByPhoneNumber/{version}'

    payload = dict()
    payload['authtoken'] = auth_token
    payload['phoneNumber'] = phone_no

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


def get_customer_acct_officer(acct_no):
    url = f'{base_url}/AccountOfficer/GetCustomerAccountOfficer/{version}'

    payload = dict()
    payload['authtoken'] = auth_token
    payload['accountNumber'] = acct_no

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


def transaction_history(**kwargs):
    url = f'{base_url}/Account/GetTransactionsPaginated/{version}'

    page_no = kwargs.get("page_no")

    payload = dict()
    payload['authtoken'] = auth_token
    payload['accountNumber'] = kwargs.get("acct_no")
    payload['fromDate'] = kwargs.get("date_from")
    payload['toDate'] = kwargs.get("date_to")
    payload['institutionCode'] = institution_code
    if page_no:
        payload['pageNo'] = page_no

    payload['PageSize'] = 10

    response = requests.request('GET', url=url, params=payload).json()
    log_request(url, payload, response)
    return response


def bvn_lookup(bvn):
    url = f'{base_url_3ps}/Account/BVN/GetBvnDetails'

    payload = dict()
    payload['token'] = auth_token
    payload['BVN'] = bvn

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def other_bank_transfer(**kwargs):
    url = f'{base_url_3ps}/Transfer/InterBankTransfer'

    amount = kwargs.get("amount") * 100

    payload = json.dumps(
        {
            "Amount": amount,
            "AppzoneAccount": kwargs.get("bank_acct_no"),
            "Payer": kwargs.get("sender_name"),
            "PayerAccountNumber": kwargs.get("sender_acct_no"),
            "ReceiverAccountNumber": kwargs.get("receiver_acct_no"),
            "ReceiverAccountType": kwargs.get("receiver_acct_type"),
            "ReceiverBankCode": kwargs.get("receiver_bank_code"),
            "ReceiverPhoneNumber": kwargs.get("receiver_phone_no"),
            "ReceiverName": kwargs.get("receiver_name"),
            "ReceiverBVN": kwargs.get("receiver_bvn"),
            "ReceiverKYC": kwargs.get("receiver_kyc"),
            "Narration": kwargs.get("description"),
            "TransactionReference": kwargs.get("trans_ref"),
            "NIPSessionID": kwargs.get("nip_session_id"),  # this is from NameEnquiry ep
            "Token": auth_token
        }
    )

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def others_name_enquiry(account_no, bank_code):
    url = f'{base_url_3ps}/Transfer/NameEnquiry'

    payload = dict()
    payload['Token'] = auth_token
    payload['BankCode'] = bank_code
    payload['AccountNumber'] = account_no

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def get_banks():
    url = f'{base_url_3ps}/BillsPayment/GetCommercialBanks/{auth_token}'

    response = requests.request('GET', url=url)
    log_request(url, response.json())
    return response


def get_customer_cards(customer_id):
    url = f'{base_url_3ps}/Cards/RetrieveCustomerCards'

    payload = dict()
    payload['Token'] = auth_token
    payload['CustomerID'] = customer_id

    response = requests.request('POST', url=url, data=payload).json()
    log_request(url, payload, response)
    return response


def freeze_or_unfreeze_card(serial_no, reason, account_no, action):
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


