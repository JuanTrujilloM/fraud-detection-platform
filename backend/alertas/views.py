from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from alertas.models import Alerta
from alertas.serializers import (
    AlertaDetalleSerializer,
    AlertaSerializer,
    ResolverAlertaSerializer,
)
from alertas.servicios import resolver_alerta
from usuarios.permisos import EsAnalista

_ALERTAS = Alerta.objects.select_related('tarjeta', 'comercio', 'autorizacion')


def _fecha(parametros, nombre):
    valor = parametros.get(nombre)
    if not valor:
        return None
    try:
        fecha = parse_date(valor)
    except ValueError:
        fecha = None
    if fecha is None:
        raise ValidationError({nombre: 'Usa el formato AAAA-MM-DD.'})
    return fecha


class AlertasView(generics.ListAPIView):
    """Bandeja de alertas: pendientes por defecto, con filtros ?tipo, ?desde, ?hasta y ?estado."""

    permission_classes = [EsAnalista]
    serializer_class = AlertaSerializer

    def get_queryset(self):
        parametros = self.request.query_params
        alertas = _ALERTAS.filter(estado=parametros.get('estado', Alerta.Estado.PENDIENTE))
        if tipo := parametros.get('tipo'):
            alertas = alertas.filter(tipo=tipo)
        if desde := _fecha(parametros, 'desde'):
            alertas = alertas.filter(fecha_creacion__date__gte=desde)
        if hasta := _fecha(parametros, 'hasta'):
            alertas = alertas.filter(fecha_creacion__date__lte=hasta)
        return alertas


class AlertaDetalleView(generics.RetrieveAPIView):
    permission_classes = [EsAnalista]
    serializer_class = AlertaDetalleSerializer
    queryset = _ALERTAS


class ResolverAlertaView(APIView):
    permission_classes = [EsAnalista]

    def post(self, request, pk):
        get_object_or_404(Alerta, pk=pk)
        entrada = ResolverAlertaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        resolver_alerta(pk, entrada.validated_data['estado'], request.user)
        return Response(AlertaSerializer(_ALERTAS.get(pk=pk)).data)
