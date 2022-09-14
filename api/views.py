from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework import status, views

from account.models import Customer, Transaction
from account.serializers import CustomerSerializer, TransactionSerializer
from account.paginations import CustomPagination
from billpayment.models import Airtime, CableTV, Data


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

        airtime_purchase_total = Airtime.objects.filter(status="success").aggregate(Sum("amount"))["amount__sum"] or 0
        data_purchase_total = Data.objects.filter(status="success").aggregate(Sum("amount"))["amount__sum"] or 0
        cable_tv_purchase_total = CableTV.objects.filter(status="success").aggregate(Sum("amount"))["amount__sum"] or 0

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
                        Q(user__username__icontains=search) | Q(customeraccount__account_no__exact=search)

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
        try:
            customer = Customer.objects.get(id=pk)
            customer.active = account_status
            customer.save()
        except Exception as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Account status changed successfully"})


class AdminTransferAPIView(views.APIView, CustomPagination):
    permission_classes = []

    def get(self, request):
        transfer_type = request.GET.get("transfer_type")
        if transfer_type == "local":
            transfers = Transaction.objects.filter(transaction_option="cit_bank_transfer").order_by('-created_on')
        elif transfer_type == "others":
            transfers = Transaction.objects.filter(transaction_option="other_bank_transfer").order_by('-created_on')
        else:
            transfers = Transaction.objects.all().order_by('-created_on')

        queryset = self.paginate_queryset(transfers, request)
        serializer = TransactionSerializer(queryset, many=True).data
        data = self.get_paginated_response(serializer).data

        return Response(data)






