from django.urls import path
from . import views

urlpatterns = [

    # path('', views.Homepage.as_view(), name="home"),
    path('login/', views.MandateLoginAPIView.as_view(), name="login"),
]
