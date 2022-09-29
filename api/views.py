from django.contrib.auth.models import User
from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework import status, views

from account.models import Customer, Transaction
from account.serializers import CustomerSerializer, TransactionSerializer
from account.paginations import CustomPagination
from billpayment.models import Airtime, CableTV, Data
from billpayment.serializers import AirtimeSerializer, DataSerializer, CableTVSerializer


class Homepage(views.APIView):
    permission_classes = []

    def get(self, request):
        data = dict()

        recent_customers = Customer.objects.all().order_by("-created_on")[:10]
        total = Customer.objects.all().count()
        recent = list()
        for customer in recent_customers:
            recent.append(customer.get_customer_detail())

        airtime_count = Airtime.objects.all().count()
        data_count = Data.objects.all().count()
        cable_tv_count = CableTV.objects.all().count()

        airtime_purchase_total = Airtime.objects.filter(status__iexact="success").aggregate(Sum("amount"))["amount__sum"] or 0
        data_purchase_total = Data.objects.filter(status__iexact="success").aggregate(Sum("amount"))["amount__sum"] or 0
        cable_tv_purchase_total = CableTV.objects.filter(status__iexact="success").aggregate(Sum("amount"))["amount__sum"] or 0

        data["recent_customer"] = recent
        data["total_customer"] = total
        data["airtime_count"] = airtime_count
        data["data_count"] = data_count
        data["cable_tv_count"] = cable_tv_count
        data["airtime_purchase_total"] = airtime_purchase_total
        data["data_purchase_total"] = data_purchase_total
        data["cable_tv_purchase_total"] = cable_tv_purchase_total

        return Response(data)


class AdminCustomerAPIView(views.APIView):
    permission_classes = []

    def get(self, request, pk=None):
        if pk:
            data = CustomerSerializer(Customer.objects.get(id=pk), context={'request': request}).data
        else:
            search = request.GET.get("search")
            account_status = request.GET.get("account_status")
            if search:
                query = Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search) | \
                        Q(user__email__icontains=search) | Q(customerID__exact=search) | \
                        Q(user__username__icontains=search) | Q(customeraccount__account_no__exact=search) | \
                        Q(phone_number__exact=search)

                customers = Customer.objects.filter(query).order_by('-created_on').distinct()
            elif account_status:
                query = Q(active=account_status)

                customers = Customer.objects.filter(query).order_by('-created_on').distinct()
            else:
                customers = Customer.objects.all().order_by('-created_on')

            data = CustomerSerializer(customers, many=True, context={'request': request}).data

        return Response(data)

    def put(self, request, pk):

        account_status = request.data.get("account_status")
        staff_status = request.data.get("staff_status")
        daily_limit = request.data.get("daily_limit")
        transfer_limit = request.data.get("transfer_limit")
        try:
            customer = Customer.objects.get(id=pk)
            if account_status:
                customer.active = account_status
            if daily_limit:
                customer.daily_limit = daily_limit
            if transfer_limit:
                customer.transfer_limit = transfer_limit
            if staff_status:
                customer.user.is_staff = staff_status
                customer.user.save()
            customer.save()
        except Exception as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Account status/limit changed successfully"})


class AdminTransferAPIView(views.APIView, CustomPagination):
    permission_classes = []

    def get(self, request):
        transfer_type = request.GET.get("transfer_type")
        search = request.GET.get("search")

        query = Q()
        if search:
            query = Q(customer__user__first_name__iexact=search) | Q(customer__user__last_name__iexact=search) | \
                     Q(customer__customerID=search) | Q(beneficiary_name__icontains=search) | \
                     Q(beneficiary_number=search) | Q(reference__iexact=search)

        if transfer_type == "local":
            query &= Q(transaction_option="cit_bank_transfer")
            transfers = Transaction.objects.filter(query).order_by('-created_on').distinct()
        elif transfer_type == "others":
            query &= Q(transaction_option="other_bank_transfer")
            transfers = Transaction.objects.filter(query).order_by('-created_on').distinct()
            print(query)
            print(transfers)
        else:
            transfers = Transaction.objects.filter(query).order_by('-created_on')

        queryset = self.paginate_queryset(transfers, request)
        serializer = TransactionSerializer(queryset, many=True).data
        data = self.get_paginated_response(serializer).data

        return Response(data)


class AdminBillPaymentAPIView(views.APIView, CustomPagination):
    permission_classes = []

    def get(self, request):

        bill_type = request.GET.get("bill_type")
        search = request.GET.get("search")

        data = dict()

        if bill_type == "airtime":
            if search:
                query = Q(account_no__iexact=search) | Q(beneficiary__iexact=search) | Q(network__iexact=search) | \
                        Q(transaction_id__iexact=search)
                queryset = Airtime.objects.filter(query).distinct().order_by('-created_on')
            else:
                queryset = Airtime.objects.all().order_by('-created_on')
            queryset = self.paginate_queryset(queryset, request)
            serializer = AirtimeSerializer(queryset, many=True).data

        if bill_type == "data":
            if search:
                query = Q(account_no__iexact=search) | Q(beneficiary__iexact=search) | Q(network__iexact=search) | \
                        Q(transaction_id__iexact=search) | Q(plan_id__iexact=search)
                queryset = Data.objects.filter(query).distinct().order_by('-created_on')
            else:
                queryset = Data.objects.all().order_by('-created_on')
            queryset = self.paginate_queryset(queryset, request)
            serializer = DataSerializer(queryset, many=True).data

        if bill_type == "cable_tv":
            if search:
                query = Q(account_no__iexact=search) | Q(service_name__iexact=search) | Q(smart_card_no__iexact=search) | \
                        Q(transaction_id__iexact=search) | Q(phone_number__iexact=search)
                queryset = CableTV.objects.filter(query).distinct().order_by('-created_on')
            else:
                queryset = CableTV.objects.all().order_by('-created_on')
            queryset = self.paginate_queryset(queryset, request)
            serializer = CableTVSerializer(queryset, many=True).data

        detail = self.get_paginated_response(serializer).data
        data["detail"] = detail

        return Response(data)




