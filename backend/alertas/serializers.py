from rest_framework import serializers

from alertas.models import Alerta
from autorizaciones.models import Autorizacion
from autorizaciones.serializers import AutorizacionAnalistaSerializer

ULTIMAS_AUTORIZACIONES = 10


class AlertaSerializer(serializers.ModelSerializer):
    tarjeta_ultimos_4 = serializers.CharField(source='tarjeta.ultimos_4', default=None)
    tarjeta_estado = serializers.CharField(source='tarjeta.estado', default=None)
    comercio_nombre = serializers.CharField(source='comercio.nombre', default=None)
    comercio_estado = serializers.CharField(source='comercio.estado', default=None)
    probabilidad_fraude = serializers.FloatField(
        source='autorizacion.probabilidad_fraude', default=None
    )

    class Meta:
        model = Alerta
        fields = [
            'id',
            'tipo',
            'autorizacion',
            'tarjeta',
            'tarjeta_ultimos_4',
            'tarjeta_estado',
            'comercio',
            'comercio_nombre',
            'comercio_estado',
            'probabilidad_fraude',
            'descripcion',
            'estado',
            'analista',
            'fecha_creacion',
            'fecha_resolucion',
        ]
        read_only_fields = fields


class AlertaDetalleSerializer(AlertaSerializer):
    ultimas_autorizaciones = serializers.SerializerMethodField()

    class Meta(AlertaSerializer.Meta):
        fields = [*AlertaSerializer.Meta.fields, 'ultimas_autorizaciones']
        read_only_fields = fields

    def get_ultimas_autorizaciones(self, alerta):
        """Las últimas autorizaciones de la tarjeta o, si no tiene, del comercio."""
        if alerta.tarjeta_id:
            filtro = {'tarjeta_id': alerta.tarjeta_id}
        elif alerta.comercio_id:
            filtro = {'comercio_id': alerta.comercio_id}
        else:
            return []
        autorizaciones = Autorizacion.objects.filter(**filtro).select_related('tarjeta', 'comercio')
        return AutorizacionAnalistaSerializer(
            autorizaciones[:ULTIMAS_AUTORIZACIONES], many=True
        ).data


class ResolverAlertaSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(
        choices=[Alerta.Estado.CONFIRMADA_FRAUDE, Alerta.Estado.DESCARTADA]
    )
