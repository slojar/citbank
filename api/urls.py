from django.urls import path
from . import views

urlpatterns = [

    path('', views.Homepage.as_view(), name="home"),
    path('customer/', views.AdminCustomerAPIView.as_view(), name="customer"),
    path('customer/<int:pk>/', views.AdminCustomerAPIView.as_view(), name="customer-detail"),
    path('transfers/', views.AdminTransferAPIView.as_view(), name="transfer"),
    path('bill/', views.AdminBillPaymentAPIView.as_view(), name="bill"),
]
