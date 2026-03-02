from django.db import models
from apps.core.models import TimeStampedModel


class Cliente(TimeStampedModel):
    nombre = models.CharField(max_length=80, blank=True)
    telefono = models.CharField(max_length=30, unique=True)  # E.164 o como lo recibas (ej: +549...)
    activo = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.nombre or 'Cliente'} ({self.telefono})"


class ConversacionEstado(models.TextChoices):
    MENU = "MENU", "Menú"
    ESPERANDO_SERVICIO = "ESPERANDO_SERVICIO", "Esperando servicio"
    ESPERANDO_FECHA = "ESPERANDO_FECHA", "Esperando fecha"
    ESPERANDO_HORA = "ESPERANDO_HORA", "Esperando hora"
    ESPERANDO_PAGO = "ESPERANDO_PAGO", "Esperando pago"
    CONFIRMADO = "CONFIRMADO", "Confirmado"
    CANCELADO = "CANCELADO", "Cancelado"


class Conversacion(TimeStampedModel):
    """
    Estado conversacional por teléfono (1 conversación activa por cliente).
    datos guarda cache temporal (servicio elegido, fecha elegida, etc.)
    """
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name="conversacion")
    estado = models.CharField(max_length=30, choices=ConversacionEstado.choices, default=ConversacionEstado.MENU)
    datos = models.JSONField(default=dict, blank=True)
    ultima_interaccion = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Conversación {self.cliente.telefono} [{self.estado}]"