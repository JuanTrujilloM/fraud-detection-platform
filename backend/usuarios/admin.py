from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from usuarios.models import Asociado, Comercio, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'rol', 'is_active', 'last_login')
    list_filter = ('rol', 'is_active')
    fieldsets = (*UserAdmin.fieldsets, ('Rol', {'fields': ('rol',)}))
    add_fieldsets = (*UserAdmin.add_fieldsets, ('Rol', {'fields': ('email', 'rol')}))


@admin.register(Asociado)
class AsociadoAdmin(admin.ModelAdmin):
    list_display = ('numero_documento', 'nombres', 'apellidos', 'ciudad', 'estado')
    list_filter = ('estado', 'ciudad')
    search_fields = ('numero_documento', 'nombres', 'apellidos')
    raw_id_fields = ('usuario',)


@admin.register(Comercio)
class ComercioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit', 'categoria', 'ciudad', 'vende_en_linea', 'estado')
    list_filter = ('estado', 'categoria', 'vende_en_linea')
    search_fields = ('nombre', 'nit')
    raw_id_fields = ('usuario',)
