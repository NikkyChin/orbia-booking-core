from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from apps.clientes.models import Cliente, Conversacion, ConversacionEstado
from apps.reservas.models import Reserva, ReservaEstado, Servicio
from apps.reservas.services import (
    calcular_hora_fin,
    generar_slots_disponibles,
    validar_slot_disponible,
)


MENU_TEXTO = (
    "Hola 👋\n"
    "1️⃣ Reservar turno\n"
    "2️⃣ Ver disponibilidad\n"
    "\n"
    "Respondé con 1 o 2."
)


def _parse_fecha(texto: str) -> Optional[date]:
    """
    Acepta:
    - YYYY-MM-DD
    - DD/MM
    - DD/MM/YYYY
    Si viene DD/MM sin año, usa año actual (y si ya pasó, asume el próximo año).
    """
    t = (texto or "").strip()

    # YYYY-MM-DD
    try:
        d = datetime.strptime(t, "%Y-%m-%d").date()
        return d
    except ValueError:
        pass

    # DD/MM o DD/MM/YYYY
    try:
        if len(t) == 5:  # DD/MM
            now = timezone.localtime(timezone.now()).date()
            d = datetime.strptime(t, "%d/%m").date().replace(year=now.year)
            if d < now:
                d = d.replace(year=now.year + 1)
            return d
        d = datetime.strptime(t, "%d/%m/%Y").date()
        return d
    except ValueError:
        return None


def _lista_servicios_activos() -> List[Servicio]:
    return list(Servicio.objects.filter(activo=True).order_by("nombre"))


def _texto_lista_servicios(servicios: List[Servicio]) -> str:
    if not servicios:
        return "No hay servicios activos configurados en este momento."
    lineas = ["Elegí un servicio:"]
    for i, s in enumerate(servicios, start=1):
        lineas.append(f"{i}️⃣ {s.nombre}")
    lineas.append("\nRespondé con el número.")
    return "\n".join(lineas)


def _texto_slots(slots) -> str:
    if not slots:
        return "No hay horarios disponibles para esa fecha. Probá otra fecha (DD/MM o YYYY-MM-DD)."
    lineas = ["Disponibilidad:"]
    for i, sl in enumerate(slots, start=1):
        lineas.append(f"{i}️⃣ {sl.inicio.strftime('%H:%M')}")
    lineas.append("\nRespondé con el número.")
    return "\n".join(lineas)


def _get_or_create_cliente_y_conversacion(telefono: str) -> Tuple[Cliente, Conversacion]:
    cliente, _ = Cliente.objects.get_or_create(telefono=telefono, defaults={"nombre": ""})
    conv, _ = Conversacion.objects.get_or_create(cliente=cliente)
    return cliente, conv


def resetear_conversacion(conv: Conversacion) -> None:
    conv.estado = ConversacionEstado.MENU
    conv.datos = {}
    conv.save(update_fields=["estado", "datos", "ultima_interaccion", "actualizado"])


def handle_inbound_message(telefono: str, texto: str) -> str:
    """
    Punto único de entrada del engine.
    Devuelve el texto a responder.
    """
    texto = (texto or "").strip()

    cliente, conv = _get_or_create_cliente_y_conversacion(telefono)

    # Comandos universales (mínimos)
    if texto.lower() in {"menu", "inicio", "volver"}:
        resetear_conversacion(conv)
        return MENU_TEXTO

    # --- Router por estado ---
    if conv.estado == ConversacionEstado.MENU:
        return _estado_menu(conv, texto)

    if conv.estado == ConversacionEstado.ESPERANDO_SERVICIO:
        return _estado_esperando_servicio(conv, texto)

    if conv.estado == ConversacionEstado.ESPERANDO_FECHA:
        return _estado_esperando_fecha(conv, texto)

    if conv.estado == ConversacionEstado.ESPERANDO_HORA:
        return _estado_esperando_hora(conv, texto)

    if conv.estado == ConversacionEstado.ESPERANDO_PAGO:
        return _estado_esperando_pago(conv, texto)

    # fallback
    resetear_conversacion(conv)
    return MENU_TEXTO


def _estado_menu(conv: Conversacion, texto: str) -> str:
    if texto == "1":
        conv.datos = {"modo": "reservar"}
        conv.estado = ConversacionEstado.ESPERANDO_SERVICIO
        conv.save(update_fields=["estado", "datos", "ultima_interaccion", "actualizado"])
        servicios = _lista_servicios_activos()
        return _texto_lista_servicios(servicios)

    if texto == "2":
        conv.datos = {"modo": "ver"}
        conv.estado = ConversacionEstado.ESPERANDO_SERVICIO
        conv.save(update_fields=["estado", "datos", "ultima_interaccion", "actualizado"])
        servicios = _lista_servicios_activos()
        return _texto_lista_servicios(servicios)

    return MENU_TEXTO


def _estado_esperando_servicio(conv: Conversacion, texto: str) -> str:
    servicios = _lista_servicios_activos()
    if not servicios:
        resetear_conversacion(conv)
        return "No hay servicios configurados. Avisá al administrador.\n\n" + MENU_TEXTO

    try:
        idx = int(texto)
    except ValueError:
        return _texto_lista_servicios(servicios)

    if idx < 1 or idx > len(servicios):
        return _texto_lista_servicios(servicios)

    servicio = servicios[idx - 1]
    conv.datos = {**(conv.datos or {}), "servicio_id": servicio.id}
    conv.estado = ConversacionEstado.ESPERANDO_FECHA
    conv.save(update_fields=["estado", "datos", "ultima_interaccion", "actualizado"])

    return "Indicá una fecha:\n- DD/MM (ej: 05/03)\n- o YYYY-MM-DD (ej: 2026-03-05)"


def _estado_esperando_fecha(conv: Conversacion, texto: str) -> str:
    d = _parse_fecha(texto)
    if not d:
        return "Fecha inválida. Usá DD/MM o YYYY-MM-DD."

    # guardo fecha
    conv.datos = {**(conv.datos or {}), "fecha": d.isoformat()}
    conv.estado = ConversacionEstado.ESPERANDO_HORA
    conv.save(update_fields=["estado", "datos", "ultima_interaccion", "actualizado"])

    servicio_id = conv.datos.get("servicio_id")
    servicio = Servicio.objects.filter(id=servicio_id, activo=True).first()
    if not servicio:
        resetear_conversacion(conv)
        return "Servicio no encontrado. Volvemos al menú.\n\n" + MENU_TEXTO

    slots = generar_slots_disponibles(fecha=d, servicio=servicio, step_min=15, limite=10)

    # guardo lista para mapear selección (solo inicios)
    conv.datos = {**(conv.datos or {}), "slots": [s.inicio.strftime("%H:%M") for s in slots]}
    conv.save(update_fields=["datos", "ultima_interaccion", "actualizado"])

    return _texto_slots(slots)


def _estado_esperando_hora(conv: Conversacion, texto: str) -> str:
    datos = conv.datos or {}
    fecha_str = datos.get("fecha")
    servicio_id = datos.get("servicio_id")
    slots = datos.get("slots") or []

    servicio = Servicio.objects.filter(id=servicio_id, activo=True).first()
    if not servicio or not fecha_str:
        resetear_conversacion(conv)
        return "Se perdió el contexto. Volvemos al menú.\n\n" + MENU_TEXTO

    try:
        idx = int(texto)
    except ValueError:
        # reimprimimos slots si el usuario mete fruta
        d = date.fromisoformat(fecha_str)
        slots_objs = generar_slots_disponibles(fecha=d, servicio=servicio, step_min=15, limite=10)
        conv.datos = {**datos, "slots": [s.inicio.strftime("%H:%M") for s in slots_objs]}
        conv.save(update_fields=["datos", "ultima_interaccion", "actualizado"])
        return _texto_slots(slots_objs)

    if idx < 1 or idx > len(slots):
        d = date.fromisoformat(fecha_str)
        slots_objs = generar_slots_disponibles(fecha=d, servicio=servicio, step_min=15, limite=10)
        conv.datos = {**datos, "slots": [s.inicio.strftime("%H:%M") for s in slots_objs]}
        conv.save(update_fields=["datos", "ultima_interaccion", "actualizado"])
        return _texto_slots(slots_objs)

    hora_txt = slots[idx - 1]
    hora_inicio = datetime.strptime(hora_txt, "%H:%M").time()
    d = date.fromisoformat(fecha_str)

    # Validación final anti-doble-reserva
    if not validar_slot_disponible(fecha=d, inicio=hora_inicio, servicio=servicio):
        # regenero y vuelvo a mostrar
        slots_objs = generar_slots_disponibles(fecha=d, servicio=servicio, step_min=15, limite=10)
        conv.datos = {**datos, "slots": [s.inicio.strftime("%H:%M") for s in slots_objs]}
        conv.save(update_fields=["datos", "ultima_interaccion", "actualizado"])
        return "Ese horario ya no está disponible.\n\n" + _texto_slots(slots_objs)

    hora_fin = calcular_hora_fin(d, hora_inicio, servicio.duracion_minutos)

    # Crear reserva + pago
    from apps.pagos.models import Pago  # import local para evitar ciclos
    from apps.pagos.services import crear_preferencia_mp

    with transaction.atomic():
        reserva = Reserva.objects.create(
            cliente=conv.cliente,
            servicio=servicio,
            fecha=d,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            estado=ReservaEstado.PENDIENTE_PAGO,
        )
        pago = Pago.objects.create(
            reserva=reserva,
            monto=servicio.precio,
            moneda="ARS",
            estado="CREADO",
            external_reference=str(reserva.id),
        )

    # Crear preferencia en MercadoPago y guardar init_point
    try:
        pago = crear_preferencia_mp(pago)
    except Exception:
        # Si falla MP, cancelamos la reserva y volvemos al menú
        reserva.marcar_cancelada()
        resetear_conversacion(conv)
        return "No pude generar el link de pago ahora. Intentá nuevamente más tarde.\n\n" + MENU_TEXTO

    # Pasamos a estado esperando pago
    conv.estado = ConversacionEstado.ESPERANDO_PAGO
    conv.datos = {"reserva_id": reserva.id}
    conv.save(update_fields=["estado", "datos", "ultima_interaccion", "actualizado"])

    fecha_h = d.strftime("%d/%m/%Y")
    hora_h = hora_inicio.strftime("%H:%M")

    return (
        f"Turno reservado para {fecha_h} a las {hora_h}.\n"
        f"Para confirmar, pagá acá:\n{pago.init_point}\n\n"
        "Cuando el pago se apruebe, queda confirmado ✅"
    )


def _estado_esperando_pago(conv: Conversacion, texto: str) -> str:
    # En v1, el webhook de MercadoPago va a confirmar y nosotros podemos avisar luego.
    # Para no agregar features: dejamos al usuario volver al menú.
    if texto.lower() in {"menu", "inicio", "volver"}:
        resetear_conversacion(conv)
        return MENU_TEXTO

    return "Estoy esperando la confirmación del pago. Escribí MENU para volver al inicio."