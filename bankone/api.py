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
    ref = 'CIT-REF-'+str(uuid.uuid4().int)[:12]

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

# def send_email_temporal_fix(to, body, subject):
#     from django.core.mail import send_mail
#     email_sender = settings.EMAIL_FROM
#     send_mail(subject=subject, message=body, from_email=email_sender, recipient_list=[to])
#     print(f"Email sent to {to}")
#

