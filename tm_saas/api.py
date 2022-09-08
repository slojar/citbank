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


