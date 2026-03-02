from django.urls import path
from .webhooks import whatsapp_webhook

urlpatterns = [
    path("webhook/", whatsapp_webhook, name="whatsapp_webhook"),
]