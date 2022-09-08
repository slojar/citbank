from django.urls import path
from . import views


urlpatterns = [
    path('network/', views.GetNetworksAPIView.as_view(), name="network"),
    path('recharge/', views.AirtimeDataPurchaseAPIView.as_view(), name="recharge"),
]
