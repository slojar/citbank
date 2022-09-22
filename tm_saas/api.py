import requests
from django.conf import settings
from bankone.api import log_request

baseUrl = settings.TM_BASE_URL
header = {
    "client-id": settings.TM_CLIENT_ID
}


def get_networks():
    url = f"{baseUrl}/data/creditswitch/networks"

    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def get_data_plan(network_name):
    url = f"{baseUrl}/data/plans?provider=creditswitch&network={network_name}"

    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def purchase_airtime(**kwargs):
    url = f"{baseUrl}/airtime"

    payload = dict()
    payload["provider"] = "creditswitch"
    payload["phoneNumber"] = kwargs.get("phone_number")
    payload["network"] = kwargs.get("network")
    payload["amount"] = kwargs.get("amount")

    response = requests.request("POST", url=url, headers=header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def purchase_data(**kwargs):
    url = f"{baseUrl}/data"

    payload = dict()
    payload["planId"] = kwargs.get("plan_id")
    payload["phoneNumber"] = kwargs.get("phone_number")
    payload["provider"] = "creditswitch"
    payload["amount"] = kwargs.get("amount")
    payload["network"] = kwargs.get("network")

    response = requests.request("POST", url=url, headers=header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def get_services(service_type):
    url = f"{baseUrl}/serviceBiller/{service_type}"

    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def get_service_products(service_name, product_code=None):
    url = f"{baseUrl}/{service_name}/products?provider=cdl"
    if product_code:
        url = f"{baseUrl}/{service_name}/addons?provider=cdl&productCode={product_code}"

    response = requests.request("GET", url=url, headers=header).json()
    log_request("GET", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def validate_scn(service_name, scn):
    url = f"{baseUrl}/{service_name}/validate"

    d_header = {
        "client-id": settings.TM_CLIENT_ID,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = f"provider=cdl&smartCardNumber={scn}"

    response = requests.request("POST", url=url, headers=d_header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {d_header}", f"payload: {payload}", f"response: {response}")
    return response


def cable_tv_sub(**kwargs):
    url = f"{baseUrl}/{kwargs.get('service_name')}/validate"

    payload = {
                "provider": "cdl",
                "monthsPaidFor": kwargs.get("duration"),
                "customerNumber": kwargs.get("customer_number"),
                "amount": kwargs.get("amount"),
                "customerName": kwargs.get("customer_name"),
                "productCodes": [kwargs.get("product_codes")],
                "invoicePeriod": kwargs.get("duration"),
                "smartcardNumber": kwargs.get("smart_card_no")
            }

    response = requests.request("POST", url=url, headers=header, data=payload).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def get_discos():
    url = f"{baseUrl}/electricity/getDiscos"
    response = requests.request("GET", url, headers=header).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"response: {response}")
    return response


def validate_meter_no(disco_type, meter_no):
    url = f"{baseUrl}/electricity/validate"

    payload = dict()
    payload["type"] = disco_type
    payload["customerReference"] = meter_no

    response = requests.request("POST", url, data=payload, headers=header).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response}")
    return response


def electricity(data):
    url = f"{baseUrl}/electricity/vend"
    response = requests.request("POST", url, data=data, headers=header).json()
    log_request("POST", f"url: {url}", f"header: {header}", f"payload: {data}", f"response: {response}")
    return response






