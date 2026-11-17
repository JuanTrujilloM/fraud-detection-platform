from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from alertas.models import Alerta
from eventos.servicios import registrar_al_confirmar
from tarjetas.models import Bloqueo
from tarjetas.servicios import bloquear_comercio
from usuarios.models import Comercio

MODULO = 'alertas'


class AlertaYaResuelta(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'La alerta ya fue resuelta.'
    default_code = 'alerta_resuelta'


def crear_alerta_modelo(autorizacion) -> Alerta:
    """Se llama dentro de la transacción de la autorización. No bloquea la tarjeta: eso lo decide
    el analista."""
    alerta = Alerta.objects.create(
        tipo=Alerta.Tipo.RIESGO_ALTO_MODELO,
        autorizacion=autorizacion,
        tarjeta=autorizacion.tarjeta,
        comercio=autorizacion.comercio,
        descripcion=(
            f'El modelo estimó una probabilidad de fraude de '
            f'{autorizacion.probabilidad_fraude:.0%} y la compra fue '
            f'{autorizacion.get_resultado_display().lower()}.'
        ),
    )
    registrar_al_confirmar(
        'ALERTA_CREADA',
        MODULO,
        None,
        {
            'id_alerta': alerta.id,
            'tipo': alerta.tipo,
            'id_autorizacion': autorizacion.id,
            'id_tarjeta': autorizacion.tarjeta_id,
            'id_comercio': autorizacion.comercio_id,
            'probabilidad_fraude': autorizacion.probabilidad_fraude,
        },
    )
    return alerta


@transaction.atomic
def crear_alerta_streaming(
    id_comercio: int, window_start, window_end, tarjetas: int, monto_promedio: float
) -> dict:
    """Recibe una prueba de tarjetas detectada por Flink: crea la alerta y bloquea el comercio.

    Flink emite varias alertas seguidas del mismo ataque (una por cada ventana que lo contiene).
    Si el comercio ya tiene una alerta de prueba de tarjetas pendiente, no se crea otra. El bloqueo
    de la fila del comercio evita que dos alertas simultáneas pasen las dos esta revisión.
    Lanza Comercio.DoesNotExist si el comercio no existe.
    """
    comercio = Comercio.objects.select_for_update().get(pk=id_comercio)
    pendiente = Alerta.objects.filter(
        comercio=comercio,
        tipo=Alerta.Tipo.PRUEBA_TARJETAS,
        estado=Alerta.Estado.PENDIENTE,
    ).exists()
    if pendiente:
        return {'creada': False}

    # Monto en pesos con separador de miles colombiano: 10000 → 10.000.
    monto = f'{monto_promedio:,.0f}'.replace(',', '.')
    alerta = Alerta.objects.create(
        tipo=Alerta.Tipo.PRUEBA_TARJETAS,
        comercio=comercio,
        descripcion=(
            f'Prueba de tarjetas: {tarjetas} tarjetas distintas con compras de ${monto} en '
            f'promedio entre {window_start:%Y-%m-%d %H:%M} y {window_end:%Y-%m-%d %H:%M} UTC.'
        ),
    )
    registrar_al_confirmar(
        'ALERTA_CREADA',
        MODULO,
        None,
        {
            'id_alerta': alerta.id,
            'tipo': alerta.tipo,
            'id_autorizacion': None,
            'id_tarjeta': None,
            'id_comercio': comercio.id,
            'probabilidad_fraude': None,
        },
    )

    comercio_bloqueado = False
    if comercio.estado != Comercio.Estado.BLOQUEADO:
        bloquear_comercio(
            comercio.id,
            origen=Bloqueo.Origen.STREAMING,
            motivo=f'Prueba de tarjetas detectada en streaming (alerta #{alerta.id})',
            usuario=None,
        )
        comercio_bloqueado = True

    return {'creada': True, 'id_alerta': alerta.id, 'comercio_bloqueado': comercio_bloqueado}


@transaction.atomic
def resolver_alerta(alerta_id: int, estado: str, analista) -> Alerta:
    alerta = Alerta.objects.select_for_update().get(pk=alerta_id)
    if alerta.estado != Alerta.Estado.PENDIENTE:
        raise AlertaYaResuelta()
    alerta.estado = estado
    alerta.analista = analista
    alerta.fecha_resolucion = timezone.now()
    alerta.save(update_fields=['estado', 'analista', 'fecha_resolucion', 'fecha_actualizacion'])
    registrar_al_confirmar(
        'ALERTA_RESUELTA', MODULO, analista, {'id_alerta': alerta.id, 'estado': alerta.estado}
    )
    return alerta
