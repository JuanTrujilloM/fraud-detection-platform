from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from tarjetas import servicios
from tarjetas.models import Bloqueo
from tarjetas.serializers import BloqueoSerializer, CrearBloqueoSerializer
from usuarios.permisos import EsAnalista


class BloqueosView(generics.ListAPIView):
    """GET: bloqueos (?vigentes=true). POST: bloquea una tarjeta o un comercio."""

    permission_classes = [EsAnalista]
    serializer_class = BloqueoSerializer

    def get_queryset(self):
        bloqueos = Bloqueo.objects.select_related('tarjeta', 'comercio')
        if self.request.query_params.get('vigentes') == 'true':
            bloqueos = bloqueos.filter(fecha_fin__isnull=True)
        return bloqueos

    def post(self, request):
        entrada = CrearBloqueoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        comunes = {
            'origen': Bloqueo.Origen.ANALISTA,
            'motivo': datos['motivo'],
            'usuario': request.user,
        }
        if datos['tipo'] == Bloqueo.Tipo.TARJETA:
            bloqueo = servicios.bloquear_tarjeta(datos['tarjeta'].id, **comunes)
        else:
            bloqueo = servicios.bloquear_comercio(datos['comercio'].id, **comunes)
        return Response(BloqueoSerializer(bloqueo).data, status=status.HTTP_201_CREATED)


class LevantarBloqueoView(APIView):
    permission_classes = [EsAnalista]

    def post(self, request, pk):
        get_object_or_404(Bloqueo, pk=pk)
        bloqueo = servicios.levantar_bloqueo(pk, request.user)
        return Response(BloqueoSerializer(bloqueo).data)
