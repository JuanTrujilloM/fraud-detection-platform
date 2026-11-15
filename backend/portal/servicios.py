from django.db import transaction
from django.utils import timezone

from eventos.servicios import registrar_al_confirmar
from portal.models import Reclamo

MODULO = 'portal'

_CAMPOS_EVENTO = {'celular': 'CELULAR', 'email': 'EMAIL'}


@transaction.atomic
def actualizar_perfil(asociado, usuario, cambios: dict) -> None:
    """Un evento CAMBIO_DATOS por campo que de verdad cambió, sin registrar los valores."""
    cambiados = [c for c, valor in cambios.items() if getattr(asociado, c) != valor]
    if not cambiados:
        return
    for campo in cambiados:
        setattr(asociado, campo, cambios[campo])
    asociado.save(update_fields=[*cambiados, 'fecha_actualizacion'])
    if 'email' in cambiados:
        usuario.email = cambios['email']
        usuario.save(update_fields=['email'])
    for campo in cambiados:
        registrar_al_confirmar(
            'CAMBIO_DATOS',
            MODULO,
            usuario,
            {'id_asociado': asociado.id, 'campo': _CAMPOS_EVENTO[campo]},
        )


@transaction.atomic
def radicar_reclamo(asociado, usuario, autorizacion, descripcion: str) -> Reclamo:
    reclamo = Reclamo.objects.create(
        asociado=asociado, autorizacion=autorizacion, descripcion=descripcion
    )
    registrar_al_confirmar(
        'RECLAMO_RADICADO',
        MODULO,
        usuario,
        {
            'id_reclamo': reclamo.id,
            'id_asociado': asociado.id,
            'id_autorizacion': autorizacion.id,
        },
    )
    return reclamo


def cambiar_estado_reclamo(reclamo: Reclamo, estado: str, resultado: str | None = None) -> Reclamo:
    resuelto = estado == Reclamo.Estado.RESUELTO
    reclamo.estado = estado
    reclamo.resultado = resultado if resuelto else None
    reclamo.fecha_resolucion = timezone.now() if resuelto else None
    reclamo.save(update_fields=['estado', 'resultado', 'fecha_resolucion', 'fecha_actualizacion'])
    return reclamo
