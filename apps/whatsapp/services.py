from __future__ import annotations

import os
from typing import Optional

from twilio.rest import Client


def normalizar_telefono(raw: str) -> str:
    """
    Twilio manda "whatsapp:+549..." (From) y para enviar también espera "whatsapp:+549..."
    Normalizamos guardando con + (sin prefijo whatsapp:), y agregamos prefijo al enviar.
    """
    if not raw:
        return ""
    raw = raw.strip()
    raw = raw.replace("whatsapp:", "")
    return raw


def _to_twilio_whatsapp(telefono: str) -> str:
    telefono = (telefono or "").strip()
    if not telefono:
        return ""
    if telefono.startswith("whatsapp:"):
        return telefono
    # guardamos en DB como +549..., Twilio quiere whatsapp:+549...
    return f"whatsapp:{telefono}"


def enviar_mensaje_whatsapp(telefono: str, texto: str) -> bool:
    """
    Envío saliente real con Twilio (WhatsApp).
    Requiere:
      - WHATSAPP_PROVIDER=twilio
      - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
    """
    provider = os.getenv("WHATSAPP_PROVIDER", "").lower().strip()
    if provider != "twilio":
        return False

    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    tw_from = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()

    if not sid or not token or not tw_from:
        return False

    to = _to_twilio_whatsapp(telefono)
    if not to:
        return False

    client = Client(sid, token)
    client.messages.create(
        from_=tw_from,
        to=to,
        body=texto or "",
    )
    return True


def crear_respuesta_twiml(texto: str) -> str:
    # Respuesta compatible con Twilio (WhatsApp)
    texto = (texto or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{texto}</Message></Response>'