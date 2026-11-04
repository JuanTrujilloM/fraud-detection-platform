from django.db.models import Exists, OuterRef
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from autorizaciones.models import Autorizacion
from portal import servicios
from portal.models import Reclamo
from portal.serializers import (
    ActualizarReclamoSerializer,
    CrearReclamoSerializer,
    MovimientoSerializer,
    PerfilSerializer,
    ReclamoSerializer,
    TarjetaAsociadoSerializer,
)
from tarjetas import servicios as servicios_tarjetas
from tarjetas.models import Bloqueo, Tarjeta
from tarjetas.serializers import BloqueoSerializer, MotivoSerializer
from usuarios.permisos import EsAnalista, EsAsociado

_RECLAMOS = Reclamo.objects.select_related(
    'asociado', 'autorizacion__comercio', 'autorizacion__tarjeta'
)


def _tarjetas_de(usuario):
    """Toda consulta del asociado parte de aquí: una tarjeta ajena responde 404, no 403, para no
    revelar que existe."""
    return Tarjeta.objects.filter(asociado=usuario.asociado)


def _tarjeta_serializada(usuario, tarjeta_id) -> dict:
    return TarjetaAsociadoSerializer(_con_puede_desbloquear(usuario).get(pk=tarjeta_id)).data


def _con_puede_desbloquear(usuario):
    propio = Bloqueo.objects.filter(
        tarjeta=OuterRef('pk'),
        fecha_fin__isnull=True,
        origen=Bloqueo.Origen.ASOCIADO,
        usuario=usuario,
    )
    return _tarjetas_de(usuario).annotate(puede_desbloquear=Exists(propio))


class MisTarjetasView(generics.ListAPIView):
    permission_classes = [EsAsociado]
    serializer_class = TarjetaAsociadoSerializer
    pagination_class = None

    def get_queryset(self):
        return _con_puede_desbloquear(self.request.user)


class MovimientosView(generics.ListAPIView):
    permission_classes = [EsAsociado]
    serializer_class = MovimientoSerializer

    def get_queryset(self):
        tarjeta = get_object_or_404(_tarjetas_de(self.request.user), pk=self.kwargs['pk'])
        return (
            Autorizacion.objects.filter(tarjeta=tarjeta)
            .select_related('comercio')
            .annotate(reclamado=Exists(Reclamo.objects.filter(autorizacion=OuterRef('pk'))))
        )


class BloquearMiTarjetaView(APIView):
    permission_classes = [EsAsociado]

    def post(self, request, pk):
        tarjeta = get_object_or_404(_tarjetas_de(request.user), pk=pk)
        entrada = MotivoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        servicios_tarjetas.bloquear_tarjeta(
            tarjeta.id,
            origen=Bloqueo.Origen.ASOCIADO,
            motivo=entrada.validated_data['motivo'],
            usuario=request.user,
        )
        return Response(_tarjeta_serializada(request.user, pk), status=status.HTTP_201_CREATED)


class DesbloquearMiTarjetaView(APIView):
    permission_classes = [EsAsociado]

    def post(self, request, pk):
        tarjeta = get_object_or_404(_tarjetas_de(request.user), pk=pk)
        bloqueo = servicios_tarjetas.desbloquear_tarjeta_asociado(tarjeta, request.user)
        return Response(
            {
                'bloqueo': BloqueoSerializer(bloqueo).data,
                'tarjeta': _tarjeta_serializada(request.user, pk),
            }
        )


class MisReclamosView(generics.ListAPIView):
    permission_classes = [EsAsociado]
    serializer_class = ReclamoSerializer

    def get_queryset(self):
        return _RECLAMOS.filter(asociado=self.request.user.asociado)

    def post(self, request):
        asociado = request.user.asociado
        entrada = CrearReclamoSerializer(data=request.data, asociado=asociado)
        entrada.is_valid(raise_exception=True)
        reclamo = servicios.radicar_reclamo(
            asociado,
            request.user,
            entrada.validated_data['autorizacion'],
            entrada.validated_data['descripcion'],
        )
        return Response(
            ReclamoSerializer(_RECLAMOS.get(pk=reclamo.pk)).data, status=status.HTTP_201_CREATED
        )


class PerfilView(APIView):
    permission_classes = [EsAsociado]

    def get(self, request):
        return Response(PerfilSerializer(request.user.asociado).data)

    def patch(self, request):
        asociado = request.user.asociado
        entrada = PerfilSerializer(asociado, data=request.data, partial=True)
        entrada.is_valid(raise_exception=True)
        servicios.actualizar_perfil(asociado, request.user, entrada.validated_data)
        return Response(PerfilSerializer(asociado).data)


class ReclamosView(generics.ListAPIView):
    """Reclamos de todos los asociados, para el analista (?estado=)."""

    permission_classes = [EsAnalista]
    serializer_class = ReclamoSerializer

    def get_queryset(self):
        estado = self.request.query_params.get('estado')
        return _RECLAMOS.filter(estado=estado) if estado else _RECLAMOS.all()


class ReclamoDetalleView(APIView):
    permission_classes = [EsAnalista]

    def patch(self, request, pk):
        reclamo = get_object_or_404(Reclamo, pk=pk)
        entrada = ActualizarReclamoSerializer(reclamo, data=request.data)
        entrada.is_valid(raise_exception=True)
        servicios.cambiar_estado_reclamo(reclamo, entrada.validated_data['estado'])
        return Response(ReclamoSerializer(_RECLAMOS.get(pk=pk)).data)
