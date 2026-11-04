from rest_framework import serializers

from autorizaciones.models import Autorizacion
from portal.models import Reclamo
from tarjetas.models import Tarjeta
from usuarios.models import Asociado


class TarjetaAsociadoSerializer(serializers.ModelSerializer):
    """Nunca expone el número completo ni el hash del CVV."""

    puede_desbloquear = serializers.BooleanField(read_only=True)

    class Meta:
        model = Tarjeta
        fields = [
            'id',
            'ultimos_4',
            'franquicia',
            'fecha_vencimiento',
            'cupo_total',
            'cupo_disponible',
            'estado',
            'puede_desbloquear',
        ]
        read_only_fields = fields


class MovimientoSerializer(serializers.ModelSerializer):
    comercio_nombre = serializers.CharField(source='comercio.nombre')
    categoria = serializers.CharField(source='comercio.categoria')
    reclamado = serializers.BooleanField(read_only=True)

    class Meta:
        model = Autorizacion
        fields = [
            'id',
            'comercio_nombre',
            'categoria',
            'monto',
            'canal',
            'resultado',
            'motivo_rechazo',
            'fecha_hora',
            'reclamado',
        ]
        read_only_fields = fields


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asociado
        fields = [
            'tipo_documento',
            'numero_documento',
            'nombres',
            'apellidos',
            'ciudad',
            'celular',
            'email',
        ]
        read_only_fields = ['tipo_documento', 'numero_documento', 'nombres', 'apellidos', 'ciudad']


class ReclamoSerializer(serializers.ModelSerializer):
    comercio_nombre = serializers.CharField(source='autorizacion.comercio.nombre')
    monto = serializers.DecimalField(source='autorizacion.monto', max_digits=14, decimal_places=2)
    fecha_compra = serializers.DateTimeField(source='autorizacion.fecha_hora')
    ultimos_4 = serializers.CharField(source='autorizacion.tarjeta.ultimos_4')
    asociado_nombre = serializers.CharField(source='asociado.__str__')

    class Meta:
        model = Reclamo
        fields = [
            'id',
            'autorizacion',
            'asociado_nombre',
            'comercio_nombre',
            'monto',
            'fecha_compra',
            'ultimos_4',
            'descripcion',
            'estado',
            'fecha_radicacion',
            'fecha_resolucion',
        ]
        read_only_fields = fields


class CrearReclamoSerializer(serializers.Serializer):
    autorizacion = serializers.PrimaryKeyRelatedField(queryset=Autorizacion.objects.none())
    descripcion = serializers.CharField(max_length=2000)

    def __init__(self, *args, asociado, **kwargs):
        super().__init__(*args, **kwargs)
        # Fuera de sus compras la autorización "no existe": no revela las de otros asociados.
        self.fields['autorizacion'].queryset = Autorizacion.objects.filter(
            tarjeta__asociado=asociado
        )

    def validate_autorizacion(self, autorizacion):
        if Reclamo.objects.filter(autorizacion=autorizacion).exists():
            raise serializers.ValidationError('Esta compra ya tiene un reclamo.')
        return autorizacion


class ActualizarReclamoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=Reclamo.Estado.choices)

    def validate_estado(self, estado):
        if self.instance.estado == Reclamo.Estado.RESUELTO and estado != Reclamo.Estado.RESUELTO:
            raise serializers.ValidationError('Un reclamo resuelto no se puede reabrir.')
        return estado
