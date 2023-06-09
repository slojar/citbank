import datetime
import decimal
import json
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import Customer
from account.utils import confirm_trans_pin, log_request
from billpayment.cron import retry_eko_elect_cron, bill_payment_reversal_cron, check_tm_saas_wallet_balance_cron
from billpayment.models import Airtime, Data, CableTV, BillPaymentReversal, Electricity
from billpayment.utils import check_balance_and_charge, vend_electricity
from coporate.models import Mandate
from tm_saas.api import get_networks, get_data_plan, purchase_airtime, purchase_data, get_services, \
    get_service_products, validate_scn, cable_tv_sub, validate_meter_no, get_discos

bank_one_banks = json.loads(settings.BANK_ONE_BANKS)


class GetNetworksAPIView(APIView):

    def get(self, request):
        try:
            data = None
            network = request.GET.get("network")
            account_type = request.GET.get("account_type", "individual")

            if account_type == "individual":
                customer = Customer.objects.get(user=request.user)
            elif account_type == "corporate":
                customer = Mandate.objects.get(user=request.user).institution
            else:
                return Response({"detail": "Invalid account type selected"}, status=status.HTTP_400_BAD_REQUEST)

            if customer.bank.tm_service_id:
                if network:
                    response = get_data_plan(str(network).lower(), customer.bank)
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
                response = get_networks(customer.bank)
                if "data" in response:
                    data = response["data"]
            else:
                return Response({"detail": "No bank available for authenticated user"},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response({"networks": data})
        except Exception as ex:
            return Response({"detail": "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class AirtimeDataPurchaseAPIView(APIView):

    def post(self, request):

        phone_number = request.data.get("phone_number")
        network = request.data.get("network")
        amount = request.data.get("amount")
        account_no = request.data.get("account_no")
        purchase_type = request.data.get("purchase_type")

        sender_type = request.data.get('sender_type', 'individual')
        bill_id = request.data.get('bill_id')

        phone_number = f"234{phone_number[-10:]}"
        narration = f"{purchase_type} purchase for {phone_number}"
        code = str(uuid.uuid4().int)[:5]

        if not all([phone_number, network, amount, purchase_type]):
            log_request(f"error-message: number, amount, network, and purchase type are required fields")
            return Response(
                {"detail": "phone_number, network, amount, and purchase_type are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        bank = success = response = payment = ref_code = None

        if sender_type == 'individual':

            success, response = confirm_trans_pin(request)
            if success is False:
                log_request(f"error-message: {response}")
                return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

            user = request.user
            try:
                customer = Customer.objects.get(user=user)
                bank = customer.bank
            except Exception as err:
                return Response({"detail": "An error has occurred", "error": str(err)},
                                status=status.HTTP_400_BAD_REQUEST)

            if customer.bank.short_name in bank_one_banks:
                name = str(customer.bank.short_name.upper())
                ref_code = f"{name}-{code}"

                success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        if sender_type == "corporate":
            try:
                if purchase_type == "airtime":
                    payment = Airtime.objects.get(id=bill_id, approved=True)
                if purchase_type == "data":
                    payment = Data.objects.get(id=bill_id, approved=True)

            except Exception as err:
                return Response({"detail": "An error has occurred", "error": str(err)},
                                status=status.HTTP_400_BAD_REQUEST)

            institution = payment.institution
            payment.bank = institution.bank
            payment.save()

            if institution.bank.short_name in bank_one_banks:
                name = str(institution.bank.short_name.upper())
                ref_code = f"{name}-{code}"

                success, response = check_balance_and_charge(None, account_no, amount, ref_code, narration, inst=institution)

            bank = institution.bank

        if success is False:
            log_request(f"error-message: {response}")
            payment.response_message = response
            payment.save()
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":
            new_success = False
            detail = "An error occurred"
            if purchase_type == "airtime":
                airtime_response = purchase_airtime(
                    bank=bank, network=network, phone_number=phone_number, amount=amount
                )

                if "error" in airtime_response:
                    # LOG REVERSAL
                    date_today = datetime.datetime.now().date()
                    BillPaymentReversal.objects.create(transaction_reference=ref_code, transaction_date=str(date_today), bank=bank)

                if "data" in airtime_response:
                    new_success = True
                    data = airtime_response["data"]

                    response_status = data["status"]
                    trans_id = data["transactionId"]
                    bill_id = data["billId"]

                    if sender_type == "individual":
                        # CREATE AIRTIME INSTANCE
                        payment = Airtime.objects.create(
                            account_no=account_no, beneficiary=phone_number, network=network, amount=amount,
                            reference=ref_code, bank=bank
                        )

                    payment.status = response_status
                    payment.transaction_id = trans_id
                    payment.bill_id = bill_id
                    payment.save()

            if purchase_type == "data":
                plan_id = request.data.get("plan_id")
                if not plan_id:
                    log_request(f"error-message: no plan selected")
                    payment.response_message = "No plan selected"
                    payment.save()
                    return Response({"detail": "Please select a plan to continue"}, status=status.HTTP_400_BAD_REQUEST)
                data_response = purchase_data(
                    bank=bank, plan_id=plan_id, phone_number=phone_number, network=network,
                    amount=amount
                )

                if "error" in data_response:
                    # LOG REVERSAL
                    date_today = datetime.datetime.now().date()
                    BillPaymentReversal.objects.create(
                        transaction_reference=ref_code, transaction_date=str(date_today), payment_type="data",
                        bank=bank
                    )

                if "data" in response:
                    new_success = True
                    data = data_response["data"]

                    response_status = data["status"]
                    trans_id = data["transactionId"]
                    bill_id = data["billId"]

                    if sender_type == "individual":
                        # CREATE DATA INSTANCE
                        payment = Data.objects.create(
                            account_no=account_no, beneficiary=phone_number, network=network, amount=amount,
                            reference=ref_code, plan_id=plan_id, bank=bank
                        )
                    payment.status = response_status
                    payment.transaction_id = trans_id
                    payment.bill_id = bill_id
                    payment.save()

            if new_success is False:
                log_request(f"error-message: {detail}")
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": f"{purchase_type} purchase for {phone_number} was successful"})

        elif response["IsSuccessful"] is True and response["ResponseCode"] == "51":
            payment.response_message = "Insufficient balance"
            payment.save()
            return Response({"detail": "Insufficient Funds"}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response(
                {"detail": "An error has occurred, please try again later"}, status=status.HTTP_400_BAD_REQUEST
            )


class CableTVAPIView(APIView):

    def get(self, request, service_name=None):

        service_type = request.GET.get("service_type")
        product_code = request.GET.get("product_code")
        account_type = request.GET.get("account_type", "individual")
        data = ""

        try:
            if account_type == "individual":
                customer = Customer.objects.get(user=request.user)
            elif account_type == "corporate":
                customer = Mandate.objects.get(user=request.user).institution
            else:
                return Response({"detail": "Invalid account type selected"}, status=status.HTTP_400_BAD_REQUEST)

            if customer.bank.short_name in bank_one_banks:
                if service_name:
                    response = get_service_products(customer.bank, service_name, product_code)
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

                    response = get_services(service_type, customer.bank)
                    if "error" in response:
                        detail = response["error"]["message"]
                        log_request(f"error-message: {detail}")
                        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
                    if "data" in response:
                        data = response["data"]["billers"]
                return Response({"detail": data})
            else:
                return Response({"detail": "No bank available for authenticated user"},
                                status=status.HTTP_400_BAD_REQUEST)
        except Exception as ex:
            return Response({"detail": "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):

        account_no = request.data.get("account_no")
        service_name = request.data.get("service_name")
        duration = request.data.get("duration")
        phone_number = request.data.get("phone_number")
        amount = request.data.get("amount")
        customer_name = request.data.get("customer_name")
        product_codes = request.data.get("product_codes")
        smart_card_no = request.data.get("smart_card_no")
        sender_type = request.data.get('sender_type', 'individual')
        bill_id = request.data.get('bill_id')

        if not all([
            account_no, service_name, smart_card_no, phone_number, amount, product_codes, duration, customer_name
        ]):
            return Response(
                {
                    "detail": "account_no, service name, smart card_no, customer number, amount, product codes, "
                              "customer name, and duration are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        code = str(uuid.uuid4().int)[:5]
        narration = f"{service_name} subscription for {smart_card_no}"
        ref_code = customer = success = response = payment = None

        if sender_type == "individual":
            success, response = confirm_trans_pin(request)
            if success is False:
                log_request(f"error-message: {response}")
                return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

            user = request.user

            try:
                customer = Customer.objects.get(user=user)
            except Exception as ex:
                return Response({"detail": "An error has occurred", "error": str(ex)},
                                status=status.HTTP_400_BAD_REQUEST)

            if customer.bank.short_name in bank_one_banks:
                amount = decimal.Decimal(amount) + customer.bank.bill_payment_charges
                s_name = str(customer.bank.short_name).upper()
                ref_code = f"{s_name}-{code}"

                success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        elif sender_type == "corporate":
            try:
                payment = CableTV.objects.get(id=bill_id, approved=True)
                institution = payment.institution
            except Exception as ex:
                return Response({"detail": "An error has occurred", "error": str(ex)},
                                status=status.HTTP_400_BAD_REQUEST)

            if institution.bank.short_name in bank_one_banks:
                amount = decimal.Decimal(amount) + institution.bank.bill_payment_charges
                s_name = str(institution.bank.short_name).upper()
                ref_code = f"{s_name}-{code}"

                success, response = check_balance_and_charge(None, account_no, amount, ref_code, narration, inst=institution)

        else:
            return Response({"detail": "Invalid sender type selected"}, status=status.HTTP_400_BAD_REQUEST)

        if success is False:
            log_request(f"error-message: {response}")
            if payment:
                payment.response_message = response
                payment.save()
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":

            # remove service charge from amount
            amount -= 100

            cable_response = cable_tv_sub(
                bank=customer.bank, service_name=service_name, duration=duration, customer_number=phone_number,
                customer_name=customer_name, amount=float(amount), product_codes=product_codes,
                smart_card_no=smart_card_no
            )

            if "error" in cable_response:
                # LOG REVERSAL
                date_today = datetime.datetime.now().date()
                BillPaymentReversal.objects.create(
                    transaction_reference=ref_code, transaction_date=str(date_today), payment_type="cableTv",
                    bank=customer.bank
                )

                Response(
                    {"detail": "An error has occurred, please try again later"}, status=status.HTTP_400_BAD_REQUEST
                )

            if "data" in cable_response:
                data = cable_response["data"]
                response_status = data["status"]
                trans_id = data["transactionId"]

                if sender_type == "individual":
                    payment = CableTV.objects.create(
                        service_name=service_name, account_no=account_no, smart_card_no=smart_card_no,
                        customer_name=customer_name, phone_number=phone_number, product=str(product_codes),
                        months=duration, amount=amount, reference=ref_code, bank=customer.bank
                    )

                payment.status = response_status
                payment.transaction_id = trans_id
                payment.save()

        elif response["IsSuccessful"] is True and response["ResponseCode"] == "51":
            log_request(f"error-message: Insufficient balance")
            payment.response_message = "Insufficient balance"
            payment.save()
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
        account_type = request.data.get("account_type", "individual")
        meter_no = request.data.get("meter_no")
        data = ""

        validate_type = request.data.get("validate_type")

        try:
            if account_type == "individual":
                customer = Customer.objects.get(user=request.user)
            elif account_type == "corporate":
                customer = Mandate.objects.get(user=request.user).institution
            else:
                return Response({"detail": "Invalid account type selected"}, status=status.HTTP_400_BAD_REQUEST)

            if customer.bank.short_name in bank_one_banks:

                if validate_type == "smart_card":
                    if not all([smart_card_no, service_name]):
                        return Response(
                            {"detail": "smart_card_no and service_name are required"}, status=status.HTTP_400_BAD_REQUEST
                        )

                    # VALIDATE SMART CARD NUMBER
                    response = validate_scn(customer.bank, service_name, smart_card_no)
                elif validate_type == "meter":
                    if not all([disco_type, meter_no]):
                        return Response(
                            {"detail": "disco_type and meter_no are required"}, status=status.HTTP_400_BAD_REQUEST
                        )

                    # VALIDATE METER NUMBER
                    response = validate_meter_no(customer.bank, disco_type, meter_no)
                else:
                    return Response({"detail": "Invalid validate_type or not selected"},
                                    status=status.HTTP_400_BAD_REQUEST)
                if "error" in response:
                    return Response({"detail": "Error validating smart card number"},
                                    status=status.HTTP_400_BAD_REQUEST)
                if "data" in response:
                    data = response["data"]
                return Response({"detail": data})
            else:
                return Response({"detail": "No bank available for authenticated user"},
                                status=status.HTTP_400_BAD_REQUEST)

        except Exception as ex:
            return Response({"detail": "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)


class ElectricityAPIView(APIView):

    def get(self, request):
        account_type = request.GET.get("account_type", "individual")

        try:
            if account_type == "individual":
                customer = Customer.objects.get(user=request.user)
            elif account_type == "corporate":
                customer = Mandate.objects.get(user=request.user).institution
            else:
                return Response({"detail": "Invalid account type selected"}, status=status.HTTP_400_BAD_REQUEST)

            if customer.bank.short_name in bank_one_banks:
                response = get_discos(customer.bank)
                if not response["data"]:
                    return Response({"detail": "An error occurred while fetching data"},
                                    status=status.HTTP_400_BAD_REQUEST)
                data = dict()
                data["detail"] = response["data"]

                return Response(data)
            else:
                return Response({"detail": "No bank available for authenticated user"},
                                status=status.HTTP_400_BAD_REQUEST)

        except Exception as ex:
            return Response({"detail": "An error has occurred", "error": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):

        disco_type = request.data.get("disco_type")
        account_no = request.data.get("account_no")
        meter_no = request.data.get("meter_no")
        amount = request.data.get("amount")
        phone_number = request.data.get("phone_no")

        sender_type = request.data.get('sender_type', 'individual')
        bill_id = request.data.get('bill_id')

        if not all([account_no, disco_type, meter_no, amount, phone_number]):
            return Response(
                {"detail": "account number, disco type, amount, phone number and meter number are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount < 1000:
            return Response({"detail": "Minimum vendible amount is 1000"}, status=status.HTTP_400_BAD_REQUEST)

        narration = f"{disco_type} payment for meter: {meter_no}"
        code = str(uuid.uuid4().int)[:5]
        bank = success = response = ref_code = payment = None

        if sender_type == "individual":
            success, detail = confirm_trans_pin(request)
            if success is False:
                return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

            user = request.user

            try:
                customer = Customer.objects.get(user=user)
            except Exception as ex:
                return Response({"detail": "An error has occurred", "error": str(ex)},
                                status=status.HTTP_400_BAD_REQUEST)

            bank = customer.bank
            if customer.bank.short_name in bank_one_banks:
                sh_name = str(customer.bank.short_name).upper()
                ref_code = f"{sh_name}-{code}"
                amount = decimal.Decimal(amount) + customer.bank.bill_payment_charges

            success, response = check_balance_and_charge(user, account_no, amount, ref_code, narration)

        elif sender_type == "corporate":
            try:
                payment = Electricity.objects.get(id=bill_id, approved=True)
                institution = payment.institution
            except Exception as ex:
                return Response({"detail": "An error has occurred", "error": str(ex)},
                                status=status.HTTP_400_BAD_REQUEST)

            bank = institution.bank
            if institution.bank.short_name in bank_one_banks:
                amount = decimal.Decimal(amount) + institution.bank.bill_payment_charges
                s_name = str(institution.bank.short_name).upper()
                ref_code = f"{s_name}-{code}"

                success, response = check_balance_and_charge(None, account_no, amount, ref_code, narration, inst=institution)
        else:
            return Response({"detail": "Invalid sender type selected"}, status=status.HTTP_400_BAD_REQUEST)

        if success is False:
            log_request(f"error-message: {response}")
            return Response({"detail": response}, status=status.HTTP_400_BAD_REQUEST)

        if response["IsSuccessful"] is True and response["ResponseCode"] == "00":

            # remove service charge from amount
            amount -= 100

            success, detail, token = vend_electricity(bank, account_no, disco_type, meter_no, amount, phone_number, ref_code, inst=payment)
            if success is False:
                # LOG REVERSAL
                date_today = datetime.datetime.now().date()
                BillPaymentReversal.objects.create(
                    transaction_reference=ref_code, transaction_date=str(date_today),
                    payment_type="electricity", bank=bank
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

        return Response(
            {"detail": f"{disco_type} payment for meter: {meter_no} was successful", "credit_token": token})


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


class CheckTMSaaSBalanceCronView(APIView):
    permission_classes = []

    def get(self, request):
        response = check_tm_saas_wallet_balance_cron()
        return Response({"detail": response})

