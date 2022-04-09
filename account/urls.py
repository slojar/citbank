from django.urls import path
from . import views


urlpatterns = [
    path('signup/', views.SignupView.as_view(), name='sign-up'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('user/', views.ViewUser.as_view(), name='login'),

]


