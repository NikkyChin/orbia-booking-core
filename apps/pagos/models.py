from django.db import models
from apps.core.models import TimeStampedModel
from apps.reservas.models import Reserva


class PagoEstado(models.TextChoices):
    CREADO = "CREADO", "Creado"
    PENDIENTE = "PENDIENTE", "Pendiente"
    APROBADO = "APROBADO", "Aprobado"
    RECHAZADO = "RECHAZADO", "Rechazado"
    CANCELADO = "CANCELADO", "Cancelado"


class Pago(TimeStampedModel):
    """
    1 Pago por Reserva (v1).
    Guarda info mínima para MP.
    """
    reserva = models.OneToOneField(Reserva, on_delete=models.CASCADE, related_name="pago")

    # MercadoPago
    mp_preference_id = models.CharField(max_length=120, blank=True)
    mp_payment_id = models.CharField(max_length=120, blank=True)  # se completa cuando MP notifica pago real
    mp_status = models.CharField(max_length=30, blank=True)

    init_point = models.URLField(blank=True)  # link de pago
    external_reference = models.CharField(max_length=80, blank=True)  # recomendado: str(reserva.id)

    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    moneda = models.CharField(max_length=10, default="ARS")

    estado = models.CharField(max_length=20, choices=PagoEstado.choices, default=PagoEstado.CREADO)

    class Meta:
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["mp_payment_id"]),
            models.Index(fields=["mp_preference_id"]),
        ]

    def __str__(self) -> str:
        return f"Pago Reserva #{self.reserva_id} [{self.estado}]"


class PagoEvento(TimeStampedModel):
    """
    Log de notificaciones de MP (webhook).
    Útil para debug y auditoría.
    """
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name="eventos", null=True, blank=True)
    topic = models.CharField(max_length=80, blank=True)
    action = models.CharField(max_length=80, blank=True)
    mp_id = models.CharField(max_length=120, blank=True)  # id recibido en webhook
    payload = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"MP Evento {self.topic}/{self.action} ({self.mp_id})"