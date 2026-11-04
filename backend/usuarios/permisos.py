from rest_framework.permissions import BasePermission

from usuarios.models import Usuario


class _TieneRol(BasePermission):
    rol: str

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == self.rol)


class EsComercio(_TieneRol):
    rol = Usuario.Rol.COMERCIO

    def has_permission(self, request, view):
        return super().has_permission(request, view) and hasattr(request.user, 'comercio')


class EsAsociado(_TieneRol):
    rol = Usuario.Rol.ASOCIADO

    def has_permission(self, request, view):
        return super().has_permission(request, view) and hasattr(request.user, 'asociado')


class EsAnalista(_TieneRol):
    rol = Usuario.Rol.ANALISTA
