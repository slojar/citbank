import json

import requests
from django.conf import settings

baseUrl = settings.TM_BASE_URL
managerUrl = settings.TM_MANAGER_SERVICE_URL


def get_header(bank):
    from account.utils import decrypt_text
    header = {
        "client-id": decrypt_text(bank.tm_service_id)
    }
    return header


def get_networks(bank):
    from account.utils import log_request
    url = f"{baseUrl}/data/creditswitch/networks"
    header = get_header(bank)
    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def get_data_plan(network_name, bank):
    from account.utils import log_request
    url = f"{baseUrl}/data/plans?provider=creditswitch&network={network_name}"
    header = get_header(bank)
    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def purchase_airtime(bank, **kwargs):
    from account.utils import log_request
    url = f"{baseUrl}/airtime"
    header = get_header(bank)
    payload = dict()
    payload["provider"] = "creditswitch"
    payload["phoneNumber"] = kwargs.get("phone_number")
    payload["network"] = kwargs.get("network")
    payload["amount"] = kwargs.get("amount")
    response = requests.request("POST", url=url, headers=header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def purchase_data(bank, **kwargs):
    from account.utils import log_request
    url = f"{baseUrl}/data"
    header = get_header(bank)
    payload = dict()
    payload["planId"] = kwargs.get("plan_id")
    payload["phoneNumber"] = kwargs.get("phone_number")
    payload["provider"] = "creditswitch"
    payload["amount"] = kwargs.get("amount")
    payload["network"] = kwargs.get("network")
    response = requests.request("POST", url=url, headers=header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def get_services(service_type, bank):
    from account.utils import log_request
    url = f"{baseUrl}/serviceBiller/{service_type}"
    header = get_header(bank)
    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def get_service_products(bank, service_name, product_code=None):
    from account.utils import log_request
    url = f"{baseUrl}/{service_name}/products?provider=cdl"
    header = get_header(bank)
    if product_code:
        url = f"{baseUrl}/{service_name}/addons?provider=cdl&productCode={product_code}"
    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def validate_scn(bank, service_name, scn):
    from account.utils import log_request, decrypt_text
    url = f"{baseUrl}/{service_name}/validate"
    d_header = {
        "client-id": decrypt_text(bank.tm_service_id),
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = f"provider=cdl&smartCardNumber={scn}"
    response = requests.request("POST", url=url, headers=d_header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {d_header}", f"payload: {payload}", f"response: {response}")
    return response


def cable_tv_sub(bank, **kwargs):
    from account.utils import log_request, decrypt_text
    url = f"{baseUrl}/{kwargs.get('service_name')}"
    # header = get_header(bank)
    header = {
        "client-id": decrypt_text(bank.tm_service_id),
        "Content-Type": "application/json"
    }

    payload = json.dumps({
                "provider": "cdl",
                "monthsPaidFor": kwargs.get("duration"),
                "customerNumber": kwargs.get("customer_number"),
                "amount": kwargs.get("amount"),
                "customerName": kwargs.get("customer_name"),
                "productCodes": kwargs.get("product_codes"),
                "invoicePeriod": kwargs.get("duration"),
                "smartcardNumber": kwargs.get("smart_card_no")
            })
    response = requests.request("POST", url=url, headers=header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def get_discos(bank):
    from account.utils import log_request
    url = f"{baseUrl}/electricity/getDiscos"
    header = get_header(bank)
    response = requests.request("GET", url, headers=header).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def validate_meter_no(bank, disco_type, meter_no):
    from account.utils import log_request
    url = f"{baseUrl}/electricity/validate"
    header = get_header(bank)
    payload = dict()
    payload["type"] = disco_type
    payload["customerReference"] = meter_no
    response = requests.request("POST", url, data=payload, headers=header).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def electricity(bank, data):
    from account.utils import log_request
    url = f"{baseUrl}/electricity/vend"
    header = get_header(bank)
    response = requests.request("POST", url, data=data, headers=header).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {data}", f"response: {response}")
    return response


def retry_electricity(bank, transaction_id):
    from account.utils import log_request
    header = get_header(bank)
    url = f"{baseUrl}/electricity/query?disco=EKEDC_PREPAID&transactionId={transaction_id}"
    response = requests.request("GET", url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def check_wallet_balance(bank):
    from account.utils import log_request, decrypt_text
    header = get_header(bank)
    client_id = decrypt_text(bank.tm_service_id)
    url = f"{managerUrl}/client/wallet/{client_id}"
    response = requests.request("GET", url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def perform_liveness_check(bank, bvn, image_url):
    from account.utils import log_request
    header = get_header(bank)
    url = f"{baseUrl}/verification/verifybvnImage"
    payload = dict()
    payload["bvn"] = bvn
    payload["image"] = image_url
    response = requests.request("POST", url, data=payload, headers=header).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response




