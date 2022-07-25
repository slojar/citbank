from django.db.models import Q
from django.shortcuts import render
from account.models import *
# Create your views here.


def dashboard(request):
    customers = Customer.objects.all()
    if 'Submit' in request.GET and request.GET.get('query'):
        var = request.GET.get('query')
        query = Q(user__first_name__icontains=var) | Q(user__last_name__icontains=var)
        query |= Q(user__username__icontains=var) | Q(customerID__iexact=var)
        query |= Q(gender__icontains=var) | Q(phone_number__iexact=var)

        customers = Customer.objects.filter(query)
    return render(request, 'superadmin/index.html', {
        'customers': customers,
    })
