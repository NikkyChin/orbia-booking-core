from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("whatsapp/", include("apps.whatsapp.urls")),
    path("pagos/", include("apps.pagos.urls")),
]