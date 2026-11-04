from django.contrib import admin

from autorizaciones.models import Autorizacion


@admin.register(Autorizacion)
class AutorizacionAdmin(admin.ModelAdmin):
    """Registro de solo lectura: las autorizaciones solo las crea el autorizador."""

    list_display = ('id', 'tarjeta', 'comercio', 'monto', 'canal', 'resultado', 'fecha_hora')
    list_filter = ('resultado', 'canal', 'motivo_rechazo')
    list_select_related = ('tarjeta', 'comercio')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
