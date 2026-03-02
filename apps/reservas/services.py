from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from django.db.models import Q
from django.utils import timezone

from apps.reservas.models import HorarioLaboral, Reserva, ReservaEstado, Servicio


@dataclass(frozen=True)
class Slot:
    inicio: time
    fin: time

    def __str__(self) -> str:
        return f"{self.inicio.strftime('%H:%M')} - {self.fin.strftime('%H:%M')}"


# ---------- Helpers de tiempo ----------

def _combine(d: date, t: time) -> datetime:
    """
    Combina fecha y hora en datetime local (naive en tu TZ actual).
    Para lógica de slots, con naive alcanza (mismo día).
    """
    return datetime.combine(d, t)


def _to_time(dt: datetime) -> time:
    return dt.time().replace(second=0, microsecond=0)


def _ceil_to_step(dt: datetime, step_min: int) -> datetime:
    """
    Redondea hacia arriba al múltiplo de step_min.
    Ej: 10:07 con step 15 -> 10:15
    """
    if step_min <= 1:
        return dt.replace(second=0, microsecond=0)
    dt = dt.replace(second=0, microsecond=0)
    minutes = dt.minute
    mod = minutes % step_min
    if mod == 0:
        return dt
    return dt + timedelta(minutes=(step_min - mod))


def _overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """
    True si [a_start, a_end) se solapa con [b_start, b_end)
    """
    return (a_start < b_end) and (b_start < a_end)


# ---------- Lógica principal ----------

def obtener_intervalos_laborales(fecha: date) -> List[Tuple[time, time]]:
    """
    Devuelve una lista de intervalos (inicio, fin) para ese día según HorarioLaboral.
    Permite múltiples rangos por día (ej: mañana y tarde).
    """
    dia_semana = fecha.weekday()  # 0=lunes ... 6=domingo
    qs = (
        HorarioLaboral.objects
        .filter(activo=True, dia_semana=dia_semana)
        .order_by("hora_inicio")
    )
    return [(h.hora_inicio, h.hora_fin) for h in qs]


def obtener_reservas_del_dia(fecha: date) -> List[Reserva]:
    """
    Trae reservas que bloquean disponibilidad (pendiente_pago + confirmada).
    Cancelada/expirada no bloquean.
    """
    return list(
        Reserva.objects
        .filter(
            fecha=fecha,
            estado__in=[ReservaEstado.PENDIENTE_PAGO, ReservaEstado.CONFIRMADA],
        )
        .order_by("hora_inicio")
    )


def generar_slots_disponibles(
    *,
    fecha: date,
    servicio: Servicio,
    step_min: int = 15,
    limite: Optional[int] = None,
) -> List[Slot]:
    """
    Genera slots disponibles para una fecha y servicio.

    - step_min: granularidad (15 recomendado)
    - limite: si querés mostrar solo los primeros N slots (ej: 8)
    """
    duracion = int(servicio.duracion_minutos)
    if duracion <= 0:
        raise ValueError("La duración del servicio debe ser > 0")

    intervalos = obtener_intervalos_laborales(fecha)
    if not intervalos:
        return []

    reservas = obtener_reservas_del_dia(fecha)

    # Si la fecha es hoy, no mostrar slots en el pasado. Redondeamos a step.
    ahora_local = timezone.localtime(timezone.now())
    es_hoy = (fecha == ahora_local.date())
    min_inicio_dt = _ceil_to_step(_combine(fecha, ahora_local.time()), step_min) if es_hoy else None

    disponibles: List[Slot] = []

    for (inicio, fin) in intervalos:
        start_dt = _combine(fecha, inicio)
        end_dt = _combine(fecha, fin)

        # Recorta si es hoy y el horario empieza antes de "ahora"
        if es_hoy and min_inicio_dt is not None and start_dt < min_inicio_dt:
            start_dt = min_inicio_dt

        # Alineamos al step
        start_dt = _ceil_to_step(start_dt, step_min)

        while True:
            slot_inicio_dt = start_dt
            slot_fin_dt = slot_inicio_dt + timedelta(minutes=duracion)

            if slot_fin_dt > end_dt:
                break

            slot_inicio = _to_time(slot_inicio_dt)
            slot_fin = _to_time(slot_fin_dt)

            # Chequeo de solape con reservas existentes
            hay_solape = False
            for r in reservas:
                if _overlap(slot_inicio, slot_fin, r.hora_inicio, r.hora_fin):
                    hay_solape = True
                    break

            if not hay_solape:
                disponibles.append(Slot(inicio=slot_inicio, fin=slot_fin))
                if limite is not None and len(disponibles) >= limite:
                    return disponibles

            # Próximo intento
            start_dt = start_dt + timedelta(minutes=step_min)

    return disponibles


def validar_slot_disponible(
    *,
    fecha: date,
    inicio: time,
    servicio: Servicio,
) -> bool:
    """
    Valida que un slot esté disponible en el momento de reservar
    (evita carreras cuando dos usuarios eligen lo mismo).
    """
    duracion = int(servicio.duracion_minutos)
    fin_dt = _combine(fecha, inicio) + timedelta(minutes=duracion)
    fin = _to_time(fin_dt)

    # Debe caer dentro de algún intervalo laboral
    intervalos = obtener_intervalos_laborales(fecha)
    dentro = any((inicio >= i and fin <= f) for (i, f) in intervalos)
    if not dentro:
        return False

    # No debe solaparse con reservas activas
    existe_solape = Reserva.objects.filter(
        fecha=fecha,
        estado__in=[ReservaEstado.PENDIENTE_PAGO, ReservaEstado.CONFIRMADA],
    ).filter(
        Q(hora_inicio__lt=fin) & Q(hora_fin__gt=inicio)
    ).exists()

    return not existe_solape


def calcular_hora_fin(fecha: date, inicio: time, duracion_minutos: int) -> time:
    fin_dt = _combine(fecha, inicio) + timedelta(minutes=int(duracion_minutos))
    return _to_time(fin_dt)