from django.urls import path
from . import views

urlpatterns = [
    path('customer/', views.AdminCustomerAPIView.as_view(), name="customer"),
]
