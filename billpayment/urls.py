from django.urls import path
from . import views


app_name = "billpayment"

urlpatterns = [
    path('network/', views.GetNetworksAPIView.as_view(), name="network"),
    path('recharge/', views.AirtimeDataPurchaseAPIView.as_view(), name="recharge"),

    path('cable/', views.CableTVAPIView.as_view(), name="cable_tv"),
    path('cable/<str:service_name>/', views.CableTVAPIView.as_view(), name="cable_tv"),
    path('validate/', views.ValidateAPIView.as_view(), name="validate"),

    path('electricity/', views.ElectricityAPIView.as_view(), name="electricity"),

    # CRON-JOBS
    path('retry-elect/', views.RetryElectricityCronView.as_view(), name="retry-elect"),
    path('bill-reversal/', views.BillPaymentReversalCronView.as_view(), name="bill-reversal"),
    path('check-balance/', views.CheckTMSaaSBalanceCronView.as_view(), name="check-balance"),
]
