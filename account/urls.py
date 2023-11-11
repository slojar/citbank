from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "account"

urlpatterns = [
    path('banks/', views.BankAPIListView.as_view(), name='banks'),
    path('open-account/', views.OpenAccountAPIView.as_view(), name='open-account'),
    path('validate-bvn/<str:bank_id>/', views.ValidateBVNAPIView.as_view(), name='validate-bvn'),

    path('dashboard/<int:bank_id>', views.CustomerDashboardAPIView.as_view(), name='dashboard'),

    path('signup/', views.SignupView.as_view(), name='sign-up'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('refresh-token/', TokenRefreshView.as_view(), name='refresh-token'),

    path('signup-otp/', views.SignupOtpView.as_view(), name='sign-up-otp'),
    path('reset-otp/', views.ResetOTPView.as_view(), name="reset-otp"),

    path('profile/', views.CustomerProfileView.as_view(), name='profile'),

    path('change-password/', views.ChangePasswordView.as_view(), name="change-password"),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name="forgot-password"),

    path('change-pin/', views.ChangeTransactionPinView.as_view(), name="change-pin"),
    path('reset-pin/', views.ResetTransactionPinView.as_view(), name='reset-transaction-pin'),

    path('transaction/', views.TransactionView.as_view(), name='user-transaction'),
    path('transaction/<str:ref>/', views.TransactionView.as_view(), name='user-transaction'),

    path('beneficiary/', views.BeneficiaryView.as_view(), name='beneficiary'),

    path('confirm-transaction-pin/', views.ConfirmTransactionPin.as_view(), name="confirm-transaction-pin"),

    path('feedback/', views.FeedbackView.as_view(), name="user-feedback"),
    # path('generate-code/', views.GenerateRandomCode.as_view(), name="generate-code"),

    path('history/<int:bank_id>', views.BankHistoryAPIView.as_view(), name="history"),
    path('statement/<int:bank_id>', views.GenerateStatement.as_view(), name="statement"),

    path('manager', views.AccountOfficerAPIView.as_view(), name="account-officer"),
    path('bank-flex/<str:bank_id>', views.BankFlexAPIView.as_view(), name="bank-flex"),

    path('transfer/<int:bank_id>/', views.TransferAPIView.as_view(), name="transfer"),
    path('name-enquiry/<int:bank_id>/', views.NameEnquiryAPIView.as_view(), name="name-enquiry"),

    path('card/', views.CardOperationAPIView.as_view(), name="cards"),
    path('fixed-deposit/<int:bank_id>', views.FixDepositAPIView.as_view(), name="fixed-deposit"),

    path('dispute/', views.RegisterDisputeAPIView.as_view(), name="dispute"),

    # Payattitude
    path('pay-with-phone/', views.PayWithPhone.as_view(), name="pay-with-phone"),
    path('validate-phone', views.ValidatePhoneNumberForPayattitude.as_view(), name="validate-phone-number"),
    path('payattitude-verify', views.StatusVerificationForPayattitude.as_view(), name="verify-payattitude"),
]


 