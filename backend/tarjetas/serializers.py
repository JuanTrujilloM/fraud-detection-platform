from rest_framework import serializers

from tarjetas.models import Bloqueo, Tarjeta
from usuarios.models import Comercio


class BloqueoSerializer(serializers.ModelSerializer):
    objetivo = serializers.SerializerMethodField()

    class Meta:
        model = Bloqueo
        fields = [
            'id',
            'tipo',
            'tarjeta',
            'comercio',
            'objetivo',
            'origen',
            'motivo',
            'usuario',
            'fecha_inicio',
            'fecha_fin',
        ]
        read_only_fields = fields

    def get_objetivo(self, bloqueo) -> str:
        return str(bloqueo.tarjeta or bloqueo.comercio)


class CrearBloqueoSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=Bloqueo.Tipo.choices)
    tarjeta = serializers.PrimaryKeyRelatedField(queryset=Tarjeta.objects.all(), required=False)
    comercio = serializers.PrimaryKeyRelatedField(queryset=Comercio.objects.all(), required=False)
    motivo = serializers.CharField(max_length=255)

    def validate(self, attrs):
        campo = 'tarjeta' if attrs['tipo'] == Bloqueo.Tipo.TARJETA else 'comercio'
        otro = 'comercio' if campo == 'tarjeta' else 'tarjeta'
        if campo not in attrs:
            raise serializers.ValidationError({campo: 'Este campo es requerido.'})
        if otro in attrs:
            raise serializers.ValidationError({otro: 'No aplica para este tipo de bloqueo.'})
        return attrs


class MotivoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255, required=False, default='Bloqueo por el titular')
