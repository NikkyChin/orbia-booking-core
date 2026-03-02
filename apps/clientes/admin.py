from django.contrib import admin
from .models import Cliente, Conversacion


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("telefono", "nombre", "activo", "creado", "actualizado")
    list_filter = ("activo",)
    search_fields = ("telefono", "nombre")
    ordering = ("-creado",)


@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = ("cliente", "estado", "ultima_interaccion", "actualizado")
    list_filter = ("estado",)
    search_fields = ("cliente__telefono", "cliente__nombre")
    ordering = ("-ultima_interaccion",)
    readonly_fields = ("creado", "actualizado", "ultima_interaccion")