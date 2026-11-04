"""Reglas de negocio de bloqueos de tarjetas y comercios."""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from eventos.servicios import registrar_al_confirmar
from tarjetas.models import Bloqueo, Tarjeta
from usuarios.models import Comercio

MODULO = 'bloqueos'


class ConflictoBloqueo(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'conflicto'


def _datos_objetivo(bloqueo: Bloqueo) -> dict:
    if bloqueo.tipo == Bloqueo.Tipo.TARJETA:
        return {'id_tarjeta': bloqueo.tarjeta_id}
    return {'id_comercio': bloqueo.comercio_id}


def _aplicar(tipo, objetivo, estado_bloqueado, *, origen, motivo, usuario) -> Bloqueo:
    bloqueo = Bloqueo.objects.create(
        tipo=tipo,
        tarjeta=objetivo if tipo == Bloqueo.Tipo.TARJETA else None,
        comercio=objetivo if tipo == Bloqueo.Tipo.COMERCIO else None,
        origen=origen,
        motivo=motivo,
        usuario=usuario,
    )
    objetivo.estado = estado_bloqueado
    objetivo.save(update_fields=['estado'])
    registrar_al_confirmar(
        'BLOQUEO_APLICADO',
        MODULO,
        usuario,
        {
            'id_bloqueo': bloqueo.id,
            'tipo': bloqueo.tipo,
            **_datos_objetivo(bloqueo),
            'origen': bloqueo.origen,
            'motivo': bloqueo.motivo,
        },
    )
    return bloqueo


@transaction.atomic
def bloquear_tarjeta(tarjeta_id: int, *, origen: str, motivo: str, usuario) -> Bloqueo:
    tarjeta = Tarjeta.objects.select_for_update().get(pk=tarjeta_id)
    if tarjeta.estado == Tarjeta.Estado.CANCELADA:
        raise ConflictoBloqueo('La tarjeta está cancelada.')
    if tarjeta.estado == Tarjeta.Estado.BLOQUEADA:
        raise ConflictoBloqueo('La tarjeta ya está bloqueada.')
    return _aplicar(
        Bloqueo.Tipo.TARJETA,
        tarjeta,
        Tarjeta.Estado.BLOQUEADA,
        origen=origen,
        motivo=motivo,
        usuario=usuario,
    )


@transaction.atomic
def bloquear_comercio(comercio_id: int, *, origen: str, motivo: str, usuario) -> Bloqueo:
    comercio = Comercio.objects.select_for_update().get(pk=comercio_id)
    if comercio.estado == Comercio.Estado.BLOQUEADO:
        raise ConflictoBloqueo('El comercio ya está bloqueado.')
    return _aplicar(
        Bloqueo.Tipo.COMERCIO,
        comercio,
        Comercio.Estado.BLOQUEADO,
        origen=origen,
        motivo=motivo,
        usuario=usuario,
    )


def _levantar(bloqueo: Bloqueo, usuario) -> Bloqueo:
    if bloqueo.fecha_fin is not None:
        raise ConflictoBloqueo('El bloqueo ya fue levantado.')

    bloqueo.fecha_fin = timezone.now()
    bloqueo.save(update_fields=['fecha_fin'])

    if bloqueo.tipo == Bloqueo.Tipo.TARJETA:
        tarjeta = Tarjeta.objects.select_for_update().get(pk=bloqueo.tarjeta_id)
        # Una tarjeta cancelada mientras estaba bloqueada sigue cancelada.
        if tarjeta.estado == Tarjeta.Estado.BLOQUEADA:
            tarjeta.estado = Tarjeta.Estado.ACTIVA
            tarjeta.save(update_fields=['estado'])
    else:
        Comercio.objects.filter(pk=bloqueo.comercio_id).update(estado=Comercio.Estado.ACTIVO)

    registrar_al_confirmar(
        'BLOQUEO_LEVANTADO',
        MODULO,
        usuario,
        {'id_bloqueo': bloqueo.id, 'tipo': bloqueo.tipo, **_datos_objetivo(bloqueo)},
    )
    return bloqueo


@transaction.atomic
def levantar_bloqueo(bloqueo_id: int, usuario) -> Bloqueo:
    """El analista puede levantar cualquier bloqueo."""
    return _levantar(Bloqueo.objects.select_for_update().get(pk=bloqueo_id), usuario)


@transaction.atomic
def desbloquear_tarjeta_asociado(tarjeta: Tarjeta, usuario) -> Bloqueo:
    """El asociado solo puede levantar los bloqueos que él mismo puso."""
    bloqueo = (
        Bloqueo.objects.select_for_update().filter(tarjeta=tarjeta, fecha_fin__isnull=True).first()
    )
    if bloqueo is None:
        raise ConflictoBloqueo('La tarjeta no tiene un bloqueo vigente.')
    if bloqueo.origen != Bloqueo.Origen.ASOCIADO or bloqueo.usuario_id != usuario.id:
        raise PermissionDenied('Este bloqueo lo puso la cooperativa; comunícate con ella.')
    return _levantar(bloqueo, usuario)
