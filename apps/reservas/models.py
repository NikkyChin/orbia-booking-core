from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.clientes.models import Cliente


class Servicio(TimeStampedModel):
    nombre = models.CharField(max_length=80)
    duracion_minutos = models.PositiveIntegerField(default=30)
    precio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.nombre


class HorarioLaboral(TimeStampedModel):
    """
    Horario semanal fijo (v1).
    dia_semana: 0=Lunes ... 6=Domingo
    """
    DIA_CHOICES = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    dia_semana = models.IntegerField(choices=DIA_CHOICES)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ("dia_semana", "hora_inicio", "hora_fin")
        ordering = ["dia_semana", "hora_inicio"]

    def __str__(self) -> str:
        return f"{self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fin}"


class ReservaEstado(models.TextChoices):
    PENDIENTE_PAGO = "PENDIENTE_PAGO", "Pendiente de pago"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    CANCELADA = "CANCELADA", "Cancelada"
    EXPIRADA = "EXPIRADA", "Expirada"


class Reserva(TimeStampedModel):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="reservas")
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="reservas")

    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    estado = models.CharField(max_length=20, choices=ReservaEstado.choices, default=ReservaEstado.PENDIENTE_PAGO)

    # Para recordatorios y trazabilidad
    recordatorio_enviado = models.BooleanField(default=False)
    cancelada_en = models.DateTimeField(null=True, blank=True)

    # Optional: referencia externa (por si integrás con algo más)
    referencia = models.CharField(max_length=80, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["fecha", "hora_inicio"]),
            models.Index(fields=["estado"]),
        ]
        ordering = ["-fecha", "-hora_inicio"]

    def __str__(self) -> str:
        return f"{self.cliente.telefono} - {self.servicio.nombre} ({self.fecha} {self.hora_inicio})"

    def marcar_cancelada(self):
        self.estado = ReservaEstado.CANCELADA
        self.cancelada_en = timezone.now()
        self.save(update_fields=["estado", "cancelada_en", "actualizado"])