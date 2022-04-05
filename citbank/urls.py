from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from django.contrib import admin
from django.urls import path


urlpatterns = [
    path('admin/', admin.site.urls),
    # Simple JWT
    path('access/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
