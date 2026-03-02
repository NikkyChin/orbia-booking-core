from __future__ import annotations

import os
from typing import Optional




def normalizar_telefono(raw: str) -> str:
    """
    Twilio manda "whatsapp:+549..." y Meta manda "549..."
    Normalizamos a algo consistente.
    """
    if not raw:
        return ""
    raw = raw.strip()
    raw = raw.replace("whatsapp:", "")
    return raw


def enviar_mensaje_whatsapp(telefono: str, texto: str) -> bool:
    """
    Stub para envío saliente.
    - Con Twilio podrías enviar por REST API.
    - Con Meta Cloud API también.
    Para v1 del engine, alcanza con responder en el webhook (Twilio) o
    implementar el envío después.
    """
    # Dejalo apagado por defecto
    provider = os.getenv("WHATSAPP_PROVIDER", "").lower().strip()
    if provider == "":
        return False

    # Si querés, después acá metemos Twilio o Meta.
    return False


def crear_respuesta_twiml(texto: str) -> str:
    # Respuesta compatible con Twilio (WhatsApp)
    # Twilio exige XML TwiML cuando respondés inline al webhook.
    texto = (texto or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{texto}</Message></Response>'