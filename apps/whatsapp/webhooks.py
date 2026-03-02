from __future__ import annotations

import json
import os

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .estados import handle_inbound_message
from .services import crear_respuesta_twiml, normalizar_telefono


def _extract_inbound(request: HttpRequest) -> tuple[str, str, str]:
    """
    Devuelve (provider, telefono, body)
    provider: "twilio" | "json" | "unknown"
    """
    # Twilio (application/x-www-form-urlencoded)
    if request.method == "POST" and request.POST.get("From") and request.POST.get("Body") is not None:
        telefono = normalizar_telefono(request.POST.get("From", ""))
        body = request.POST.get("Body", "")
        return "twilio", telefono, body

    # JSON genérico
    try:
        raw = request.body.decode("utf-8") if request.body else ""
        data = json.loads(raw) if raw else {}
        # Intentamos campos comunes
        telefono = normalizar_telefono(
            data.get("from") or data.get("telefono") or data.get("phone") or ""
        )
        body = data.get("text") or data.get("body") or data.get("mensaje") or ""
        if telefono and body is not None:
            return "json", telefono, str(body)
    except Exception:
        pass

    return "unknown", "", ""


@csrf_exempt
def whatsapp_webhook(request: HttpRequest) -> HttpResponse:
    # Verificación estilo Meta (opcional; no molesta si no lo usás)
    if request.method == "GET":
        verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and challenge and (verify_token and token == verify_token):
            return HttpResponse(challenge)
        return HttpResponse("ok")

    provider, telefono, body = _extract_inbound(request)

    if provider == "unknown" or not telefono:
        return JsonResponse({"ok": False, "error": "payload_no_reconocido"}, status=400)

    respuesta = handle_inbound_message(telefono=telefono, texto=body)

    # Respuesta inline para Twilio
    if provider == "twilio":
        xml = crear_respuesta_twiml(respuesta)
        return HttpResponse(xml, content_type="application/xml")

    # Respuesta genérica JSON
    return JsonResponse({"ok": True, "to": telefono, "reply": respuesta})