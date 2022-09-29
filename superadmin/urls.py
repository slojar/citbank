from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from superadmin.views import dashboard

app_name = "superadmin"

urlpatterns = [
    path('', dashboard, name="index"),
]



