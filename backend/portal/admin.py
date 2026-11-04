from django.contrib import admin

from portal.models import Reclamo


@admin.register(Reclamo)
class ReclamoAdmin(admin.ModelAdmin):
    list_display = ('id', 'asociado', 'autorizacion', 'estado', 'fecha_radicacion')
    list_filter = ('estado',)
    raw_id_fields = ('asociado', 'autorizacion')
