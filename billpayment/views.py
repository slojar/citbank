import datetime
import uuid
from threading import Thread

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import Customer, CustomerAccount
from bankone.api import get_account_by_account_no, get_account_info, charge_customer, log_reversal
from billpayment.models import Airtime, Data
from tm_saas.api import get_networks, get_data_plan, purchase_airtime, purchase_data


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

        # CONFIRM CUSTOMER OWNS THE ACCOUNT
        if not CustomerAccount.objects.filter(customer__user=request.user, active=True, account_no=account_no).exists():
            return Response({"detail": "Account not found"}, status=status.HTTP_400_BAD_REQUEST)

        # CHECK ACCOUNT BALANCE
        account_no = 1300224922
        response = get_account_info(account_no).json()
        balance = response["AvailableBalance"]

        if balance == 0:
            return Response({"detail": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)

        if float(amount) > balance:
            return Response(
                {"detail": "Amount cannot be greater than current balance"}, status=status.HTTP_400_BAD_REQUEST
            )

        # CHARGE CUSTOMER ACCOUNT
        code = str(uuid.uuid4().int)[:5]
        ref_code = f"CIT-{code}"

        narration = f"{purchase_type} purchase for {phone_number}"
        response = charge_customer(account_no=account_no, amount=amount, trans_ref=ref_code, description=narration)
        response = response.json()

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
