from django.urls import path
from .webhooks import mp_webhook

urlpatterns = [
    path("mp/webhook/", mp_webhook, name="mp_webhook"),
]