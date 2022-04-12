from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


urlpatterns = [
    path('', views.home, name="home"),
    path('account/signup/', views.SignupView.as_view(), name='sign-up'),
    path('account/login/', views.LoginView.as_view(), name='login'),
    path('account/refresh-token/', TokenRefreshView.as_view(), name='refresh-token'),
    path('account/signup-otp/', views.SignupOtpView.as_view(), name='sign-up-otp'),

]


