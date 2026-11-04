from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from alertas.models import Alerta
from eventos.servicios import registrar_al_confirmar

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
def resolver_alerta(alerta_id: int, estado: str, analista) -> Alerta:
    alerta = Alerta.objects.select_for_update().get(pk=alerta_id)
    if alerta.estado != Alerta.Estado.PENDIENTE:
        raise AlertaYaResuelta()
    alerta.estado = estado
    alerta.analista = analista
    alerta.fecha_resolucion = timezone.now()
    alerta.save(update_fields=['estado', 'analista', 'fecha_resolucion'])
    registrar_al_confirmar(
        'ALERTA_RESUELTA', MODULO, analista, {'id_alerta': alerta.id, 'estado': alerta.estado}
    )
    return alerta
