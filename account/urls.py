from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


urlpatterns = [
    path('signup/', views.SignupView.as_view(), name='sign-up'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('refresh-token/', TokenRefreshView.as_view(), name='refresh-token'),
    path('signup-otp/', views.SignupOtpView.as_view(), name='sign-up-otp'),
    path('profile/', views.CustomerProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name="change-password")
]


