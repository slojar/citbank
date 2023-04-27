from django.urls import path
from . import views

app_name = "coporate"

urlpatterns = [
    path('login/', views.MandateLoginAPIView.as_view(), name="login"),
    path('dashboard/', views.MandateDashboardAPIView.as_view(), name="dashboard"),
    path('account-officer/', views.InstitutionAccountOfficer.as_view(), name="officer"),
    path('limit/', views.TransferLimitAPIView.as_view(), name="limit"),
    path('change-password/', views.MandateChangePasswordAPIView.as_view(), name="change-password"),
    path('send-token/', views.SendOTPAPIView.as_view(), name="send-otp"),
    path('transfer-request/', views.TransferRequestAPIView.as_view(), name="transfer-request"),
    path('transfer-request/<int:pk>/', views.TransferRequestAPIView.as_view(), name="transfer-request-detail"),
    path('bill-payment/', views.CorporateBillPaymentAPIView.as_view(), name='bill-payment'),
    path('bill-payment/<int:pk>/', views.CorporateBillPaymentAPIView.as_view(), name='bill-payment-detail'),

    # SCHEDULED JOBS
    path('scheduler/', views.TransferSchedulerAPIView.as_view(), name="transfer-scheduler"),
    path('scheduler/<int:pk>/', views.TransferSchedulerAPIView.as_view(), name="transfer-scheduler"),

    # Bulk Operations
    path('upload/', views.BulkUploadAPIView.as_view(), name="bulk-transfer-upload"),
    path('bulk-payment/', views.BulkBillPaymentAPIView.as_view(), name="bulk-payment"),
    path('bulk-payment/<int:pk>/', views.BulkBillPaymentAPIView.as_view(), name="bulk-payment-detail"),
    path('bulk-transfer/', views.BulkTransferAPIView.as_view(), name="bulk-transfer"),
    path('bulk-transfer/<int:pk>/', views.BulkTransferAPIView.as_view(), name="bulk-transfer-detail"),

    # CRON-JOBS
    path('transfer-cron/', views.TransferRequestCronView.as_view(), name="transfer-cron"),
    path('delete-upload/', views.DeleteUploadedFiles.as_view(), name="delete-upload"),

]
