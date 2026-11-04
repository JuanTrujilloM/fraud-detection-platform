from dataclasses import asdict

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from autorizaciones.models import Autorizacion
from autorizaciones.serializers import AutorizacionComercioSerializer, SolicitudCompraSerializer
from autorizaciones.servicios import autorizar
from eventos.contexto import obtener_contexto
from usuarios.permisos import EsComercio


class AutorizarCompraView(APIView):
    """El comercio sale del token: solo se puede autorizar a su propio nombre.

    Un rechazo es una decisión de negocio exitosa, así que también responde 200.
    """

    permission_classes = [EsComercio]

    def post(self, request):
        entrada = SolicitudCompraSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        decision = autorizar(
            entrada.a_solicitud(),
            request.user.comercio,
            request.user,
            obtener_contexto(request),
        )
        return Response(asdict(decision))


class HistorialComercioView(generics.ListAPIView):
    permission_classes = [EsComercio]
    serializer_class = AutorizacionComercioSerializer

    def get_queryset(self):
        return Autorizacion.objects.filter(comercio=self.request.user.comercio).select_related(
            'tarjeta'
        )
