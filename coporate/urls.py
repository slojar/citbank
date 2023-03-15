from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.MandateLoginAPIView.as_view(), name="login"),
    path('dashboard/', views.MandateDashboardAPIView.as_view(), name="dashboard"),
    path('account-officer/', views.InstitutionAccountOfficer.as_view(), name="officer"),
    path('limit/', views.TransferLimitAPIView.as_view(), name="limit"),
    path('transfer-request/', views.TransferRequestAPIView.as_view(), name="transfer-request"),
    path('transfer-request/<int:pk>/', views.TransferRequestAPIView.as_view(), name="transfer-request-detail"),
]
