from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.pagos.models import Pago, PagoEvento, PagoEstado
from apps.pagos.services import obtener_payment_mp, actualizar_pago_desde_payment
from apps.reservas.models import ReservaEstado


@csrf_exempt
def mp_webhook(request: HttpRequest) -> JsonResponse:
    """
    MercadoPago manda distintos formatos según integración.
    Soportamos:
    - query params: ?type=payment&data.id=123
    - json body: {"type":"payment","data":{"id":"123"}}
    También a veces manda "topic" en vez de "type".
    """
    topic = request.GET.get("type") or request.GET.get("topic") or ""
    data_id = request.GET.get("data.id") or request.GET.get("id") or ""

    body = {}
    if request.body:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = {}

    if not data_id:
        data = body.get("data") or {}
        data_id = data.get("id") or body.get("id") or ""

    if not topic:
        topic = body.get("type") or body.get("topic") or ""

    # Guardamos evento para auditoría
    PagoEvento.objects.create(
        pago=None,
        topic=str(topic),
        action=str(body.get("action") or ""),
        mp_id=str(data_id),
        payload=body or {},
    )

    # Solo nos interesa payment
    if str(topic).lower() != "payment" or not data_id:
        return JsonResponse({"ok": True})

    # Consultamos el payment real (fuente de verdad)
    payment_data = obtener_payment_mp(str(data_id))

    external_reference = str(payment_data.get("external_reference") or "").strip()
    mp_pref_id = str(payment_data.get("order", {}).get("id") or "").strip()  # no siempre viene
    mp_payment_id = str(payment_data.get("id") or "").strip()

    # Buscamos Pago por mp_payment_id o external_reference
    pago = None

    if mp_payment_id:
        pago = Pago.objects.filter(mp_payment_id=mp_payment_id).first()

    if not pago and external_reference.isdigit():
        pago = Pago.objects.filter(external_reference=external_reference).select_related("reserva").first()

    if not pago:
        # No encontramos, igual respondemos ok para que MP no reintente infinito
        return JsonResponse({"ok": True, "warning": "pago_no_encontrado"})

    # Asociamos evento al pago
    PagoEvento.objects.create(
        pago=pago,
        topic="payment",
        action=str(body.get("action") or ""),
        mp_id=str(data_id),
        payload=payment_data or {},
    )

    with transaction.atomic():
        pago = actualizar_pago_desde_payment(pago, payment_data)

        # Si se aprobó, confirmamos la reserva
        if pago.estado == PagoEstado.APROBADO:
            reserva = pago.reserva
            if reserva.estado != ReservaEstado.CONFIRMADA:
                reserva.estado = ReservaEstado.CONFIRMADA
                reserva.save(update_fields=["estado", "actualizado"])

    return JsonResponse({"ok": True})