from django.contrib import admin
from .models import Servicio, HorarioLaboral, Reserva


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "duracion_minutos", "precio", "activo", "actualizado")
    list_filter = ("activo",)
    search_fields = ("nombre",)
    ordering = ("nombre",)


@admin.register(HorarioLaboral)
class HorarioLaboralAdmin(admin.ModelAdmin):
    list_display = ("dia_semana", "hora_inicio", "hora_fin", "activo")
    list_filter = ("dia_semana", "activo")
    ordering = ("dia_semana", "hora_inicio")


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "hora_inicio", "hora_fin", "servicio", "cliente", "estado", "recordatorio_enviado")
    list_filter = ("estado", "fecha", "servicio", "recordatorio_enviado")
    search_fields = ("cliente__telefono", "cliente__nombre", "servicio__nombre")
    ordering = ("-fecha", "-hora_inicio")
    readonly_fields = ("creado", "actualizado", "cancelada_en")