from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


urlpatterns = [
    path('signup/', views.HomepageView.as_view(), name='homepage'),
    path('signup/', views.SignupView.as_view(), name='sign-up'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('refresh-token/', TokenRefreshView.as_view(), name='refresh-token'),
    path('signup-otp/', views.SignupOtpView.as_view(), name='sign-up-otp'),
    path('profile/', views.CustomerProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name="change-password"),
    path('reset-otp/', views.ResetOTPView.as_view(), name="reset-otp"),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name="forgot-password"),
    path('change-pin/', views.ChangeTransactionPinView.as_view(), name="change-pin"),
    path('reset-pin/', views.ResetTransactionPinView.as_view(), name='reset-transaction-pin'),
    path('transaction/', views.TransactionView.as_view(), name='user-transaction'),
    path('transaction/<str:ref>/', views.TransactionView.as_view(), name='user-transaction'),
    path('beneficiary/', views.BeneficiaryView.as_view(), name='beneficiary'),
    path('confirm-transaction-pin/', views.ConfirmTransactionPin.as_view(), name="confirm-transaction-pin"),

    path('feedback/', views.FeedbackView.as_view(), name="user-feedback"),
    path('generate-code/', views.GenerateRandomCode.as_view(), name="generate-code"),
]


 