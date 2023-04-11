from django.urls import path
from . import views

urlpatterns = [

    path('', views.Homepage.as_view(), name="home"),
    path('<str:bank_id>/customer', views.AdminCustomerAPIView.as_view(), name="customer"),
    path('<str:bank_id>/customer/<int:pk>', views.AdminCustomerAPIView.as_view(), name="customer-detail"),
    path('<str:bank_id>/transfers/', views.AdminTransferAPIView.as_view(), name="transfer"),
    path('<str:bank_id>/bill-payment/', views.AdminBillPaymentAPIView.as_view(), name="bill"),
    path('<str:bank_id>/account-request/', views.AdminAccountRequestAPIView.as_view(), name="account-request"),
    path('<str:bank_id>/account-request/<int:pk>/', views.AdminAccountRequestAPIView.as_view(), name="acct-req-detail"),

    # Corporate Account
    # path('roles/', views.CorporateRoleListAPIView.as_view(), name="roles"),
    path('mandate/', views.CorporateUserAPIView.as_view(), name="corporate-user"),
    path('mandate/<int:pk>/', views.CorporateUserAPIView.as_view(), name="corporate-user-detail"),
    path('institution/', views.InstitutionAPIView.as_view(), name="institution"),
    path('institution/<int:pk>/', views.InstitutionAPIView.as_view(), name="institution-detail"),
]
