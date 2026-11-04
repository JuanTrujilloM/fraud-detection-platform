import re
from decimal import Decimal

from rest_framework import serializers

from autorizaciones.models import Autorizacion
from autorizaciones.servicios import SolicitudCompra

Canal = Autorizacion.Canal
ModoLectura = Autorizacion.ModoLectura

_CAMPOS_EN_LINEA = ('cvv', 'huella_dispositivo', 'segundos_formulario', 'tarjeta_pegada')


class SolicitudCompraSerializer(serializers.Serializer):
    """Entrada de POST /api/autorizaciones/. Los errores nunca repiten el número ni el CVV."""

    numero_tarjeta = serializers.RegexField(r'^\d{13,19}$')
    fecha_vencimiento = serializers.RegexField(r'^(0[1-9]|1[0-2])/\d{2}$', help_text='MM/AA')
    monto = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    canal = serializers.ChoiceField(choices=Canal.choices)
    modo_lectura = serializers.ChoiceField(choices=ModoLectura.choices)
    cvv = serializers.RegexField(r'^\d{3,4}$', required=False, write_only=True)
    huella_dispositivo = serializers.CharField(max_length=64, required=False)
    segundos_formulario = serializers.FloatField(min_value=0, required=False)
    tarjeta_pegada = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if attrs['canal'] == Canal.EN_LINEA:
            faltantes = {
                c: 'Requerido en compras en línea.' for c in _CAMPOS_EN_LINEA if c not in attrs
            }
            if faltantes:
                raise serializers.ValidationError(faltantes)
            if attrs['modo_lectura'] != ModoLectura.DIGITADA:
                raise serializers.ValidationError(
                    {'modo_lectura': 'Las compras en línea son digitadas.'}
                )
        elif attrs['modo_lectura'] == ModoLectura.DIGITADA:
            raise serializers.ValidationError(
                {'modo_lectura': 'Las compras presenciales son con chip o banda.'}
            )
        return attrs

    def a_solicitud(self) -> SolicitudCompra:
        datos = self.validated_data
        mes, anio = re.fullmatch(r'(\d{2})/(\d{2})', datos['fecha_vencimiento']).groups()
        return SolicitudCompra(
            numero_tarjeta=datos['numero_tarjeta'],
            mes_vencimiento=int(mes),
            anio_vencimiento=2000 + int(anio),
            monto=datos['monto'],
            canal=datos['canal'],
            modo_lectura=datos['modo_lectura'],
            cvv=datos.get('cvv'),
            huella_dispositivo=datos.get('huella_dispositivo'),
            segundos_formulario=datos.get('segundos_formulario'),
            tarjeta_pegada=datos.get('tarjeta_pegada'),
        )


class AutorizacionComercioSerializer(serializers.ModelSerializer):
    ultimos_4 = serializers.CharField(source='tarjeta.ultimos_4')

    class Meta:
        model = Autorizacion
        fields = [
            'id',
            'ultimos_4',
            'monto',
            'canal',
            'modo_lectura',
            'resultado',
            'motivo_rechazo',
            'fecha_hora',
        ]
        read_only_fields = fields


class AutorizacionAnalistaSerializer(serializers.ModelSerializer):
    ultimos_4 = serializers.CharField(source='tarjeta.ultimos_4')
    comercio_nombre = serializers.CharField(source='comercio.nombre')

    class Meta:
        model = Autorizacion
        fields = [
            'id',
            'tarjeta',
            'ultimos_4',
            'comercio',
            'comercio_nombre',
            'monto',
            'canal',
            'modo_lectura',
            'resultado',
            'motivo_rechazo',
            'probabilidad_fraude',
            'ip',
            'fecha_hora',
        ]
        read_only_fields = fields
