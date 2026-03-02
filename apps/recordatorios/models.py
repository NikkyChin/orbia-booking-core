from django.db import models

# V1: no necesitamos modelos.
# Los recordatorios se generan consultando apps.reservas.Reserva
# (ej: confirmadas para mañana y recordatorio_enviado=False).