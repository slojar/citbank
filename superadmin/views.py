from django.shortcuts import render
from account import models
# Create your views here.


def dashboard(request):
    customers = models.Customer.objects.all()
    return render(request, 'superadmin/index.html', {
        'customers': customers,
    })
