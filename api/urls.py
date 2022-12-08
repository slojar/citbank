from django.urls import path
from . import views

urlpatterns = [

    path('', views.Homepage.as_view(), name="home"),
    path('<str:bank_id>/customer', views.AdminCustomerAPIView.as_view(), name="customer"),
    path('<str:bank_id>/customer/<int:pk>', views.AdminCustomerAPIView.as_view(), name="customer-detail"),
    path('<str:bank_id>/transfers/', views.AdminTransferAPIView.as_view(), name="transfer"),
    path('<str:bank_id>/bill-payment/', views.AdminBillPaymentAPIView.as_view(), name="bill"),
]
