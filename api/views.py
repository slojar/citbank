from django.db.models import Q
from rest_framework.response import Response
from rest_framework import status, views

from account.models import Customer
from account.serializers import CustomerSerializer
from account.paginations import CustomPagination


class AdminCustomerAPIView(views.APIView):
    permission_classes = []

    def get(self, request, pk=None):
        if pk:
            customer_id = request.GET.get("customer_id")
            data = CustomerSerializer(Customer.objects.get(id=customer_id), context={'request': request}).data
        else:
            search = request.GET.get("search")
            account_status = request.GET.get("account_status")
            if search:
                query = Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search) | \
                        Q(user__email__icontains=search) | Q(customerID__exact=search) | \
                        Q(user__username__icontains=search) | Q(customeraccount__account_no__exact=search)

                customers = Customer.objects.filter(query).order_by('-created_on')
            elif account_status:
                query = Q(active=account_status)

                customers = Customer.objects.filter(query).order_by('-created_on')
            else:
                customers = Customer.objects.all().order_by('-created_on')

            data = CustomerSerializer(customers, many=True, context={'request': request}).data

        recent_customers = Customer.objects.all().order_by("-created_on")[:10]
        total = Customer.objects.all().count()
        recent = list()
        for customer in recent_customers:
            recent.append(customer.get_customer_detail())
        return Response({"detail": data, "recent": recent, "count": total})

    def put(self, request, pk):

        account_status = request.data.get("account_status")
        try:
            customer = Customer.objects.get(id=pk)
            customer.active = account_status
            customer.save()
        except Exception as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Account status changed successfully"})





