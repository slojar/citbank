import uuid

import requests, logging
from django.conf import settings

base_url = settings.BANK_ONE_BASE_URL
version = settings.BANK_ONE_VERSION
auth_token = settings.BANK_ONE_AUTH_TOKEN
institution_code = settings.CIT_INSTITUTION_CODE


def log_request(*args):
    for arg in args:
        logging.info(arg)


def get_account_by_account_no(account_no):
    url = base_url+'/Customer/GetByAccountNo/'+version

    payload = dict()
    payload['authtoken'] = auth_token
    payload['accountNumber'] = account_no

    response = requests.request('GET', url=url, params=payload)
    log_request(url, payload, response.json())
    return response


def send_sms(account_no, content, receiver):
    url = base_url+'/Messaging/SaveBulkSms/'+f'{version}?authtoken={auth_token}&institutionCode={institution_code}'
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




