from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include

urlpatterns = [
    path("", lambda request: HttpResponse("OK"), name="home"),
    path("admin/", admin.site.urls),
    path("whatsapp/", include("apps.whatsapp.urls")),
    path("pagos/", include("apps.pagos.urls")),
]