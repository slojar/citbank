import requests
from django.conf import settings

base_url = settings.BANK_ONE_BASE_URL
version = settings.BANK_ONE_VERSION
auth_token = settings.BANK_ONE_AUTH_TOKEN


def get_account_by_account_no(account_no):
    url = base_url+'/Account/GetAccountByAccountNumber/'+version

    payload = dict()
    payload['authtoken'] = auth_token
    payload['accountNumber'] = account_no

    response = requests.request('GET', url=url, params=payload)
    return response


def get_customer_info_by_customer_id(customer_id):
    url = base_url+'/Customer/GetCustomerInfoByCustomerID/'+version

    payload = dict()
    payload['authtoken'] = auth_token
    payload['customerID'] = customer_id

    response = requests.request('GET', url=url, params=payload)
    return response.json()




