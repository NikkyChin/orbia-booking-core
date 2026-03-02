from django.contrib import admin
from .models import Pago, PagoEvento


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("reserva", "estado", "monto", "moneda", "mp_status", "actualizado")
    list_filter = ("estado", "moneda")
    search_fields = ("reserva__cliente__telefono", "mp_payment_id", "mp_preference_id")
    ordering = ("-actualizado",)
    readonly_fields = ("creado", "actualizado")


@admin.register(PagoEvento)
class PagoEventoAdmin(admin.ModelAdmin):
    list_display = ("pago", "topic", "action", "mp_id", "creado")
    list_filter = ("topic", "action")
    search_fields = ("mp_id", "pago__mp_payment_id", "pago__mp_preference_id")
    ordering = ("-creado",)
    readonly_fields = ("creado", "actualizado", "payload")