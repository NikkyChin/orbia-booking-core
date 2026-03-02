from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.reservas.models import Reserva, ReservaEstado


class Command(BaseCommand):
    help = "Expira reservas pendientes de pago antiguas para liberar disponibilidad."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutos",
            type=int,
            default=30,
            help="Minutos de antigüedad para considerar una reserva pendiente como expirable (default 30).",
        )

    def handle(self, *args, **options):
        minutos = int(options["minutos"])
        limite = timezone.now() - timedelta(minutes=minutos)

        qs = Reserva.objects.filter(
            estado=ReservaEstado.PENDIENTE_PAGO,
            creado__lt=limite,
        )

        count = qs.update(estado=ReservaEstado.EXPIRADA)
        self.stdout.write(self.style.SUCCESS(f"Reservas expiradas: {count} (>{minutos} min)"))