import datetime
import decimal
import uuid
from threading import Thread

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import Customer, CustomerAccount
from account.utils import confirm_trans_pin
from bankone.api import log_request
from billpayment.cron import retry_eko_elect_cron, bill_payment_reversal_cron
from billpayment.models import Airtime, Data, CableTV, BillPaymentReversal
from billpayment.utils import check_balance_and_charge, vend_electricity
from tm_saas.api import get_networks, get_data_plan, purchase_airtime, purchase_data, get_services, \
    get_service_products, validate_scn, cable_tv_sub, validate_meter_no, get_discos


class GetNetworksAPIView(APIView):

    def get(self, request):

        data = None
        network = request.GET.get("network")

        if network:
            response = get_data_plan(str(network).lower())
            if "data" in response:
                data_plans = list()
                for item in response["data"]:
                    data = dict()
                    data["plan_name"] = item["name"]
                    data["plan_price"] = item["price"]
                    data["plan_validity"] = item["validity"]
                    data["plan_id"] = item["planId"]
                    data_plans.append(data)

                return Response({"data_plans": data_plans})

        response = get_networks()
        if "data" in response:
            data = response["data"]

        return Response({"networks": data})


class AirtimeDataPurchaseAPIView(APIView):

    def post(self, request):

        phone_number = request.data.get("phone_number")
        network = request.data.get("network")
        amount = request.data.get("amount")
        account_no = request.data.get("account_no")
        purchase_type = request.data.get("purchase_type")

        if not all([phone_number, network, amount, purchase_type]):
            log_request(f"error-message: number, amount, network, and purchase type are required fields")
            return Response(
                {"detail": "phone_number, network, amount, and purchase_type are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        success, response = confirm_trans_pin(request)
        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = f"234{phone_number[-10:]}"

        narration = f"{purchase_type} purchase for {phone_number}"
        code = str(uuid.uuid4().int)[:5]
        ref_code = f"CIT-{code}"
        user = request.user

        success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":
            new_success = False
            detail = "An error occurred"
            if purchase_type == "airtime":
                response = purchase_airtime(network=network, phone_number=phone_number, amount=amount)

                if "error" in response:
                    # LOG REVERSAL
                    date_today = datetime.datetime.now().date()
                    BillPaymentReversal.objects.create(transaction_reference=ref_code, transaction_date=str(date_today))

                if "data" in response:
                    new_success = True
                    data = response["data"]

                    response_status = data["status"]
                    trans_id = data["transactionId"]
                    bill_id = data["billId"]

                    # CREATE AIRTIME INSTANCE
                    Airtime.objects.create(
                        account_no=account_no, beneficiary=phone_number, network=network, amount=amount,
                        status=response_status, transaction_id=trans_id, bill_id=bill_id, reference=ref_code
                    )

            if purchase_type == "data":
                plan_id = request.data.get("plan_id")
                if not plan_id:
                    log_request(f"error-message: no plan selected")
                    return Response({"detail": "Please select a plan to continue"}, status=status.HTTP_400_BAD_REQUEST)
                response = purchase_data(plan_id=plan_id, phone_number=phone_number, network=network, amount=amount)

                if "error" in response:
                    # LOG REVERSAL
                    date_today = datetime.datetime.now().date()
                    BillPaymentReversal.objects.create(
                        transaction_reference=ref_code, transaction_date=str(date_today), payment_type="data"
                    )

                if "data" in response:
                    new_success = True
                    data = response["data"]

                    response_status = data["status"]
                    trans_id = data["transactionId"]
                    bill_id = data["billId"]

                    # CREATE DATA INSTANCE
                    Data.objects.create(
                        account_no=account_no, beneficiary=phone_number, network=network, amount=amount, reference=ref_code,
                        status=response_status, transaction_id=trans_id, bill_id=bill_id, plan_id=plan_id
                    )

            if new_success is False:
                log_request(f"error-message: {detail}")
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": f"{purchase_type} purchase for {phone_number} was successful"})

        elif response["IsSuccessful"] is True and response["ResponseCode"] == "51":
            return Response({"detail": "Insufficient Funds"}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response(
                {"detail": "An error has occurred, please try again later"}, status=status.HTTP_400_BAD_REQUEST
            )


class CableTVAPIView(APIView):

    def get(self, request, service_name=None):

        service_type = request.GET.get("service_type")
        product_code = request.GET.get("product_code")
        data = ""

        if service_name:
            response = get_service_products(service_name, product_code)
            if "error" in response:
                detail = response["error"]
                log_request(f"error-message: {detail}")
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            if "data" in response:
                data = response["data"]

        else:
            if not service_type:
                log_request("error-message: service type is required")
                return Response({"detail": "service_type is required"}, status=status.HTTP_400_BAD_REQUEST)

            response = get_services(service_type)
            if "error" in response:
                detail = response["error"]["message"]
                log_request(f"error-message: {detail}")
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            if "data" in response:
                data = response["data"]["billers"]
        return Response({"detail": data})

    def post(self, request):

        account_no = request.data.get("account_no")
        service_name = request.data.get("service_name")
        duration = request.data.get("duration")
        phone_number = request.data.get("phone_number")
        amount = request.data.get("amount")
        customer_name = request.data.get("customer_name")
        product_codes = request.data.get("product_codes")
        smart_card_no = request.data.get("smart_card_no")

        if not all([account_no, service_name, smart_card_no, phone_number, amount, product_codes, duration]):
            return Response(
                {
                    "detail": "account_no, service_name, smart_card_no, customer_number, amount, product_codes, "
                              "and duration are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        success, response = confirm_trans_pin(request)
        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        code = str(uuid.uuid4().int)[:5]
        narration = f"{service_name} subscription for {smart_card_no}"
        ref_code = f"CIT-{code}"
        user = request.user

        amount = decimal.Decimal(amount) + decimal.Decimal(settings.SERVICE_CHARGE)

        success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":

            # remove service charge from amount
            amount -= 100

            response = cable_tv_sub(
                service_name=service_name, duration=duration, customer_number=phone_number,
                customer_name=customer_name, amount=amount, product_codes=product_codes, smart_card_no=smart_card_no
            )

            if "error" in response:
                # LOG REVERSAL
                date_today = datetime.datetime.now().date()
                BillPaymentReversal.objects.create(
                    transaction_reference=ref_code, transaction_date=str(date_today), payment_type="cableTv"
                )

                Response(
                    {"detail": "An error has occurred, please try again later"}, status=status.HTTP_400_BAD_REQUEST
                )

            if "data" in response:
                data = response["data"]

                response_status = data["status"]
                trans_id = data["transactionId"]

                # CREATE CABLE TV INSTANCE
                CableTV.objects.create(
                    service_name=service_name, account_no=account_no, smart_card_no=smart_card_no,
                    customer_name=customer_name, phone_number=phone_number, product=str(product_codes), months=duration,
                    amount=amount, status=response_status, transaction_id=trans_id, reference=ref_code
                )

        elif response["IsSuccessful"] is True and response["ResponseCode"] == "51":
            log_request(f"error-message: Insufficient balance")
            return Response({"detail": "Insufficient Funds"}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response(
                {"detail": "An error has occurred, please try again later"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"detail": f"{service_name} subscription for {smart_card_no} was successful"})


class ValidateAPIView(APIView):

    def post(self, request):
        smart_card_no = request.data.get("smart_card_no")
        service_name = request.data.get("service_name")
        disco_type = request.data.get("disco_type")
        meter_no = request.data.get("meter_no")
        data = ""

        validate_type = request.data.get("validate_type")

        if validate_type == "smart_card":
            if not all([smart_card_no, service_name]):
                return Response(
                    {"detail": "smart_card_no and service_name are required"}, status=status.HTTP_400_BAD_REQUEST
                )

            # VALIDATE SMART CARD NUMBER
            response = validate_scn(service_name, smart_card_no)
        elif validate_type == "meter":
            if not all([disco_type, meter_no]):
                return Response(
                    {"detail": "disco_type and meter_no are required"}, status=status.HTTP_400_BAD_REQUEST
                )

            # VALIDATE METER NUMBER
            response = validate_meter_no(disco_type, meter_no)
        else:
            return Response({"detail": "Invalid validate_type or not selected"}, status=status.HTTP_400_BAD_REQUEST)

        if "error" in response:
            return Response({"detail": "Error validating smart card number"}, status=status.HTTP_400_BAD_REQUEST)
        if "data" in response:
            data = response["data"]
        return Response({"detail": data})


class ElectricityAPIView(APIView):

    def get(self, request):
        response = get_discos()
        if not response["data"]:
            return Response({"detail": "An error occurred while fetching data"}, status=status.HTTP_400_BAD_REQUEST)

        data = dict()
        data["detail"] = response["data"]

        return Response(data)

    def post(self, request):

        disco_type = request.data.get("disco_type")
        account_no = request.data.get("account_no")
        meter_no = request.data.get("meter_no")
        amount = request.data.get("amount")
        phone_number = request.data.get("phone_no")

        if not all([account_no, disco_type, meter_no, amount, phone_number]):
            return Response(
                {"detail": "account number, disco type, amount, phone number and meter number are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        success, detail = confirm_trans_pin(request)
        if success is False:
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        narration = f"{disco_type} payment for meter: {meter_no}"
        code = str(uuid.uuid4().int)[:5]
        ref_code = f"CIT-{code}"
        user = request.user

        amount = decimal.Decimal(amount) + decimal.Decimal(settings.SERVICE_CHARGE)

        success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":

            # remove service charge from amount
            amount -= 100

            success, detail, token = vend_electricity(account_no, disco_type, meter_no, amount, phone_number, ref_code)
            if success is False:
                # LOG REVERSAL
                date_today = datetime.datetime.now().date()
                BillPaymentReversal.objects.create(
                    transaction_reference=ref_code, transaction_date=str(date_today), payment_type="electricity"
                )
                return Response(
                    {"detail": "An error while vending electricity, please try again later"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        elif response["IsSuccessful"] is True and response["ResponseCode"] == "51":
            return Response({"detail": "Insufficient Funds"}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response(
                {"detail": "An error has occurred, please try again later"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"detail": f"{disco_type} payment for meter: {meter_no} was successful", "credit_token": token})


class RetryElectricityCronView(APIView):
    permission_classes = []

    def get(self, request):
        response = retry_eko_elect_cron()
        return Response({"detail": response})


class BillPaymentReversalCronView(APIView):
    permission_classes = []

    def get(self, request):
        response = bill_payment_reversal_cron()
        return Response({"detail": response})


