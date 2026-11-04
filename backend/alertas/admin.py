from django.contrib import admin

from alertas.models import Alerta


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'estado', 'tarjeta', 'comercio', 'fecha_creacion')
    list_filter = ('estado', 'tipo')
    raw_id_fields = ('autorizacion', 'tarjeta', 'comercio', 'analista')
