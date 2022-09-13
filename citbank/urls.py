from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from account.views import HomepageView, RerouteView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomepageView.as_view()),
    path('bankone/', RerouteView.as_view()),
    path('account/', include("account.urls")),
    path('superadmin/', include('superadmin.urls')),
    path('bills/', include('billpayment.urls')),
    path('api/', include('api.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


