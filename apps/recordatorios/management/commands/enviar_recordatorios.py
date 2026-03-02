from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.reservas.models import Reserva, ReservaEstado
from apps.whatsapp.services import enviar_mensaje_whatsapp


class Command(BaseCommand):
    help = "Envía recordatorios de turnos confirmados (para mañana) y marca recordatorio_enviado."

    def handle(self, *args, **options):
        hoy = timezone.localtime(timezone.now()).date()
        manana = hoy + timedelta(days=1)

        qs = Reserva.objects.filter(
            fecha=manana,
            estado=ReservaEstado.CONFIRMADA,
            recordatorio_enviado=False,
        ).select_related("cliente", "servicio")

        count = 0
        for r in qs:
            msg = (
                f"Recordatorio 👋\n"
                f"Tenés turno mañana ({r.fecha.strftime('%d/%m/%Y')}) a las {r.hora_inicio.strftime('%H:%M')}.\n"
                f"Servicio: {r.servicio.nombre}\n\n"
                f"Si no podés asistir, respondé MENU para volver al inicio."
            )

            # En v1, si no tenés envío saliente implementado, igual marcamos para no spamear
            enviado = enviar_mensaje_whatsapp(r.cliente.telefono, msg)

            r.recordatorio_enviado = True
            r.save(update_fields=["recordatorio_enviado", "actualizado"])
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Recordatorios procesados: {count}"))