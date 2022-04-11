import requests, logging
from django.conf import settings

base_url = settings.BANK_ONE_BASE_URL
version = settings.BANK_ONE_VERSION
auth_token = settings.BANK_ONE_AUTH_TOKEN


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





