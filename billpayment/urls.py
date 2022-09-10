from django.urls import path
from . import views

urlpatterns = [
    path('network/', views.GetNetworksAPIView.as_view(), name="network"),
    path('recharge/', views.AirtimeDataPurchaseAPIView.as_view(), name="recharge"),

    path('cable/', views.CableTVAPIView.as_view(), name="cable_tv"),
    path('cable/<str:service_name>/', views.CableTVAPIView.as_view(), name="cable_tv"),
    path('validate-scn/', views.ValidateSCNAPIView.as_view(), name="validate-scn"),
]