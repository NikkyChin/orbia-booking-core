from __future__ import annotations

import os
from decimal import Decimal
from typing import Optional

import mercadopago
from django.conf import settings
from django.urls import reverse

from apps.pagos.models import Pago, PagoEstado


def _public_base_url() -> str:
    """
    Base pública para webhooks (ej: https://tuapp.com).
    En dev podés usar ngrok o tu dominio.
    """
    base = os.getenv("PUBLIC_BASE_URL", "").strip()
    if not base:
        # fallback: intenta usar SITE_URL si lo tenés
        base = getattr(settings, "SITE_URL", "").strip()
    return base.rstrip("/")


def crear_preferencia_mp(pago: Pago) -> Pago:
    """
    Crea preferencia en MercadoPago y guarda:
    - mp_preference_id
    - init_point
    - estado -> PENDIENTE
    """
    access_token = os.getenv("MP_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise RuntimeError("Falta MP_ACCESS_TOKEN en variables de entorno")

    base_url = _public_base_url()
    if not base_url:
        raise RuntimeError("Falta PUBLIC_BASE_URL (necesario para notification_url de MP)")

    sdk = mercadopago.SDK(access_token)

    reserva = pago.reserva
    servicio = reserva.servicio

    notification_url = f"{base_url}{reverse('mp_webhook')}"

    # MercadoPago suele trabajar con float, pero cuidamos Decimal -> float
    monto = float(Decimal(pago.monto))

    preference_data = {
        "items": [
            {
                "title": f"Reserva - {servicio.nombre}",
                "quantity": 1,
                "currency_id": pago.moneda or "ARS",
                "unit_price": monto,
            }
        ],
        "external_reference": pago.external_reference or str(reserva.id),
        "notification_url": notification_url,
        # Podés limitar métodos si querés, pero no agregamos nada extra acá.
    }

    result = sdk.preference().create(preference_data)

    if not result or result.get("status") not in (200, 201):
        raise RuntimeError(f"MercadoPago preference create failed: {result}")

    pref = result.get("response", {}) or {}
    pago.mp_preference_id = str(pref.get("id", "") or "")
    pago.init_point = str(pref.get("init_point", "") or "")
    pago.estado = PagoEstado.PENDIENTE
    pago.save(update_fields=["mp_preference_id", "init_point", "estado", "actualizado"])
    return pago


def actualizar_pago_desde_payment(pago: Pago, payment_data: dict) -> Pago:
    """
    Actualiza Pago según respuesta del payment (GET /v1/payments/{id})
    """
    status = (payment_data.get("status") or "").lower().strip()

    pago.mp_status = status
    pago.mp_payment_id = str(payment_data.get("id", "") or "")

    if status == "approved":
        pago.estado = PagoEstado.APROBADO
    elif status in {"rejected", "cancelled"}:
        pago.estado = PagoEstado.RECHAZADO if status == "rejected" else PagoEstado.CANCELADO
    else:
        pago.estado = PagoEstado.PENDIENTE

    pago.save(update_fields=["mp_status", "mp_payment_id", "estado", "actualizado"])
    return pago


def obtener_payment_mp(payment_id: str) -> dict:
    access_token = os.getenv("MP_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise RuntimeError("Falta MP_ACCESS_TOKEN en variables de entorno")

    sdk = mercadopago.SDK(access_token)
    result = sdk.payment().get(payment_id)

    if not result or result.get("status") != 200:
        raise RuntimeError(f"MercadoPago payment get failed: {result}")

    return result.get("response", {}) or {}