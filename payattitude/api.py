import requests
import json
from django.conf import settings
from account.utils import log_request, decrypt_text

baseUrl = settings.PAYATTITUDE_BASE_URL


def get_header(client_id):
    header = json.dumps({"clientID": str(client_id), "Content-Type": "application/json"})
    return header


def single_register(client_id, f_name, l_name, phone, m_name, bvn, accout_no):
    url = f"{baseUrl}/register/single"
    header = get_header(client_id)
    payload = json.dumps({
        "FirstName": str(f_name),
        "LastName": str(l_name),
        "Phone": str(phone),
        "MiddleName": str(m_name),
        "Bvn": str(bvn),
        "Account": str(accout_no)
    })
    log_request(f"LOGGING PAYATTITUDE REQUEST\nURL: {url}\nHEADER: {header}\nPAYLOAD: {payload}")
    response = requests.request("POST", url=url, headers=header, data=payload)
    log_request(f"LOGGING PAYATTITUDE RESPONSE\nRESPONSE: {response.text}")
    # log_request("POST", f"url: {url}", f"header: {header}", f"payload: {payload}", f"response: {response.text}")
    return response.json()





