import datetime
import uuid
from threading import Thread

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import Customer, CustomerAccount
from bankone.api import get_account_by_account_no, get_account_balance, charge_customer, log_reversal
from billpayment.models import Airtime, Data
from billpayment.utils import check_balance_and_charge
from tm_saas.api import get_networks, get_data_plan, purchase_airtime, purchase_data, get_services, \
    get_service_products, validate_scn, cable_tv_sub


class GetNetworksAPIView(APIView):
    permission_classes = []

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
            return Response(
                {"detail": "phone_number, network, amount, and purchase_type are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = f"234{phone_number[-10:]}"

        narration = f"{purchase_type} purchase for {phone_number}"
        code = str(uuid.uuid4().int)[:5]
        ref_code = f"CIT-{code}"
        user = request.user

        success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        if success is False:
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":
            if purchase_type == "airtime":
                response = purchase_airtime(network=network, phone_number=phone_number, amount=amount)

                if "error" in response:
                    # LOG REVERSAL
                    date_today = datetime.datetime.now().date()
                    Thread(target=log_reversal, args=[date_today, ref_code]).start()

                    Response({"detail": "An error has occurred"}, status=status.HTTP_400_BAD_REQUEST)

                data = response["data"]

                response_status = data["status"]
                trans_id = data["transactionId"]
                bill_id = data["billId"]

                # CREATE AIRTIME INSTANCE
                airtime = Airtime.objects.create(
                    account_no=account_no, beneficiary=phone_number, network=network, amount=amount,
                    status=response_status, transaction_id=trans_id, bill_id=bill_id
                )

            if purchase_type == "data":
                plan_id = request.data.get("plan_id")
                if not plan_id:
                    return Response({"detail": "Please select a plan to continue"}, status=status.HTTP_400_BAD_REQUEST)
                response = purchase_data(plan_id=plan_id, phone_number=phone_number, network=network, amount=amount)

                if "error" in response:
                    # LOG REVERSAL
                    date_today = datetime.datetime.now().date()
                    Thread(target=log_reversal, args=[date_today, ref_code]).start()

                    Response({"detail": "An error has occurred"}, status=status.HTTP_400_BAD_REQUEST)

                data = response["data"]

                response_status = data["status"]
                trans_id = data["transactionId"]
                bill_id = data["billId"]

                # CREATE DATA INSTANCE
                data = Data.objects.create(
                    account_no=account_no, beneficiary=phone_number, network=network, amount=amount,
                    status=response_status, transaction_id=trans_id, bill_id=bill_id, plan_id=plan_id
                )
        else:
            return Response(
                {"detail": "An error has occurred, please try again later"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"detail": f"{purchase_type} purchase for {phone_number} was successful"})


class CableTVAPIView(APIView):
    permission_classes = []

    def get(self, request, service_name=None):

        service_type = request.GET.get("service_type")
        product_code = request.GET.get("product_code")

        if service_name:
            response = get_service_products(service_name, product_code)
            if "error" in response:
                detail = response["error"]
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

            data = response["data"]

        else:
            if not service_type:
                return Response({"detail": "service_type is required"}, status=status.HTTP_400_BAD_REQUEST)

            response = get_services(service_type)
            if "error" in response:
                detail = response["error"]["message"]
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

            data = response["data"]["billers"]
        return Response({"detail": data})

    def post(self, request):

        account_no = request.data.get("account_no")
        service_name = request.data.get("service_name")
        duration = request.data.get("duration")
        customer_number = request.data.get("customer_number")
        amount = request.data.get("amount")
        customer_name = request.data.get("customer_name")
        product_codes = request.data.get("product_codes")
        smart_card_no = request.data.get("smart_card_no")

        if not all([account_no, service_name, smart_card_no, customer_number, amount, product_codes, duration]):
            return Response(
                {
                    "detail": "account_no, service_name, smart_card_no, customer_number, amount, product_codes, "
                              "and duration are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        code = str(uuid.uuid4().int)[:5]
        narration = f"{service_name} subscription for {smart_card_no}"
        ref_code = f"CIT-{code}"
        user = request.user

        success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        if success is False:
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":

            response = cable_tv_sub(
                service_name=service_name, duration=duration, customer_number=customer_number,
                customer_name=customer_name, amount=amount, product_codes=product_codes, smart_card_no=smart_card_no
            )

            if "error" in response:
                # LOG REVERSAL
                date_today = datetime.datetime.now().date()
                Thread(target=log_reversal, args=[date_today, ref_code]).start()

                Response({"detail": "An error has occurred"}, status=status.HTTP_400_BAD_REQUEST)

            # data = response["data"]
            #
            # response_status = data["status"]
            # trans_id = data["transactionId"]
            # bill_id = data["billId"]

            # CREATE CABLE TV INSTANCE
            # airtime = Airtime.objects.create(
            #     account_no=account_no, beneficiary=phone_number, network=network, amount=amount,
            #     status=response_status, transaction_id=trans_id, bill_id=bill_id
            # )

            pass

        return Response({})


class ValidateSCNAPIView(APIView):

    def post(self, request):
        smart_card_no = request.data.get("smart_card_no")
        service_name = request.data.get("service_name")

        if not all([smart_card_no, service_name]):
            return Response({"detail": "smart_card_no and service_name are required"})

        # VALIDATE SMART CARD NUMBER
        response = validate_scn(service_name, smart_card_no)
        if "error" in response:
            return Response({"detail": "Error validating smart card number"}, status=status.HTTP_400_BAD_REQUEST)

        data = response["data"]
        return Response({"detail": data})




