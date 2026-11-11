"""El autorizador: decide cada compra dentro de la petición.

Valida en orden, de lo más barato a lo más costoso, y rechaza en la primera validación que falle.
Todo corre en una transacción con la fila de la tarjeta bloqueada, para que dos compras simultáneas
no se pasen del cupo.
"""

import time
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from alertas.servicios import crear_alerta_modelo
from autorizaciones.modelo import VERSION_MODELO, ConsultaModelo, consultar_modelo
from autorizaciones.models import Autorizacion
from eventos.contexto import ContextoPeticion
from eventos.servicios import registrar_al_confirmar
from tarjetas.cvv import cvv_coincide
from tarjetas.models import Tarjeta
from usuarios.models import Comercio

MODULO = 'autorizador'
Motivo = Autorizacion.MotivoRechazo
Canal = Autorizacion.Canal
Resultado = Autorizacion.Resultado


@dataclass(frozen=True)
class SolicitudCompra:
    numero_tarjeta: str
    mes_vencimiento: int
    anio_vencimiento: int
    monto: Decimal
    canal: str
    modo_lectura: str
    cvv: str | None = None
    huella_dispositivo: str | None = None
    segundos_formulario: float | None = None
    tarjeta_pegada: bool | None = None


@dataclass(frozen=True)
class Decision:
    id_autorizacion: int | None
    resultado: str
    motivo_rechazo: str | None


def _validar_vencimiento(solicitud: SolicitudCompra, tarjeta: Tarjeta) -> str | None:
    vence = tarjeta.fecha_vencimiento
    if (solicitud.anio_vencimiento, solicitud.mes_vencimiento) != (vence.year, vence.month):
        return Motivo.DATOS_INVALIDOS
    hoy = timezone.localdate()
    if (hoy.year, hoy.month) > (vence.year, vence.month):
        return Motivo.TARJETA_VENCIDA
    return None


def _primera_falla(
    solicitud: SolicitudCompra, comercio: Comercio, tarjeta: Tarjeta | None
) -> str | None:
    """Validaciones 1 a 7. Devuelve el motivo de la primera que falle."""
    en_linea = solicitud.canal == Canal.EN_LINEA

    if comercio.estado != Comercio.Estado.ACTIVO:
        return Motivo.COMERCIO_BLOQUEADO
    if en_linea and not comercio.vende_en_linea:
        return Motivo.CANAL_NO_PERMITIDO
    if tarjeta is None:
        return Motivo.TARJETA_INEXISTENTE
    if tarjeta.estado == Tarjeta.Estado.BLOQUEADA:
        return Motivo.TARJETA_BLOQUEADA
    if tarjeta.estado == Tarjeta.Estado.CANCELADA:
        return Motivo.TARJETA_CANCELADA
    motivo = _validar_vencimiento(solicitud, tarjeta)
    if motivo:
        return motivo
    if en_linea and not cvv_coincide(tarjeta.numero, solicitud.cvv or '', tarjeta.cvv_hash):
        return Motivo.CVV_INVALIDO
    if solicitud.monto > tarjeta.cupo_disponible:
        return Motivo.CUPO_INSUFICIENTE
    return None


def _variables_modelo(
    solicitud: SolicitudCompra, comercio: Comercio, tarjeta: Tarjeta, contexto: ContextoPeticion
) -> dict:
    return {
        'monto': float(solicitud.monto),
        'canal': solicitud.canal,
        'modo_lectura': solicitud.modo_lectura,
        'categoria': comercio.categoria,
        'ciudad_comercio': comercio.ciudad,
        'cupo_total': float(tarjeta.cupo_total),
        'cupo_disponible': float(tarjeta.cupo_disponible),
        'tiene_chip': tarjeta.tiene_chip,
        'ingreso_anual': float(tarjeta.asociado.ingreso_anual),
        'puntaje_crediticio': tarjeta.asociado.puntaje_crediticio,
        'ciudad_asociado': tarjeta.asociado.ciudad,
        'tipo_dispositivo': contexto.tipo_dispositivo,
        'huella_dispositivo': solicitud.huella_dispositivo,
        'segundos_formulario': solicitud.segundos_formulario,
        'tarjeta_pegada': solicitud.tarjeta_pegada,
    }


def _decidir_con_modelo(probabilidad: float | None) -> tuple[str | None, bool]:
    """Devuelve el motivo de rechazo (si lo hay) y si hay que crear una alerta."""
    if probabilidad is None:
        return None, False
    if probabilidad >= settings.UMBRAL_RECHAZO_MODELO:
        return Motivo.RIESGO_ALTO, True
    if probabilidad >= settings.UMBRAL_ALERTA_MODELO:
        return None, True
    return None, False


def _datos_evento(
    solicitud: SolicitudCompra,
    comercio: Comercio,
    contexto: ContextoPeticion,
    autorizacion: Autorizacion | None,
    tarjeta: Tarjeta | None,
    resultado: str,
    motivo: str | None,
    consulta: ConsultaModelo | None,
) -> dict:
    # La tarjeta se identifica por id, bin y últimos 4; nunca por el número completo.
    en_linea = solicitud.canal == Canal.EN_LINEA
    return {
        'id_autorizacion': autorizacion.id if autorizacion else None,
        'id_tarjeta': tarjeta.id if tarjeta else None,
        'bin': solicitud.numero_tarjeta[:6],
        'ultimos_4': solicitud.numero_tarjeta[-4:],
        'id_comercio': comercio.id,
        'categoria': comercio.categoria,
        'ciudad_comercio': comercio.ciudad,
        'monto': solicitud.monto,
        'canal': solicitud.canal,
        'modo_lectura': solicitud.modo_lectura,
        'resultado': resultado,
        'motivo_rechazo': motivo,
        'probabilidad_fraude': consulta.probabilidad if consulta else None,
        'ip': contexto.ip,
        'tipo_dispositivo': contexto.tipo_dispositivo,
        'navegador': contexto.navegador,
        'sistema_operativo': contexto.sistema_operativo,
        'huella_dispositivo': solicitud.huella_dispositivo if en_linea else None,
        'segundos_formulario': solicitud.segundos_formulario if en_linea else None,
        'tarjeta_pegada': solicitud.tarjeta_pegada if en_linea else None,
        'tiempo_modelo_ms': consulta.tiempo_ms if consulta else None,
        'version_modelo': VERSION_MODELO if consulta and consulta.disponible else None,
    }


def autorizar(
    solicitud: SolicitudCompra, comercio: Comercio, usuario, contexto: ContextoPeticion
) -> Decision:
    inicio = time.perf_counter()

    with transaction.atomic():
        tarjeta = (
            Tarjeta.objects.select_for_update(of=('self',))
            .select_related('asociado')
            .filter(numero=solicitud.numero_tarjeta)
            .first()
        )

        motivo = _primera_falla(solicitud, comercio, tarjeta)
        consulta = None
        crear_alerta = False
        if motivo is None:
            consulta = consultar_modelo(_variables_modelo(solicitud, comercio, tarjeta, contexto))
            motivo, crear_alerta = _decidir_con_modelo(consulta.probabilidad)

        resultado = Resultado.RECHAZADA if motivo else Resultado.APROBADA

        # Las compras con tarjeta inexistente quedan solo en el log.
        autorizacion = None
        if tarjeta is not None:
            autorizacion = Autorizacion.objects.create(
                tarjeta=tarjeta,
                comercio=comercio,
                monto=solicitud.monto,
                canal=solicitud.canal,
                modo_lectura=solicitud.modo_lectura,
                resultado=resultado,
                motivo_rechazo=motivo,
                probabilidad_fraude=consulta.probabilidad if consulta else None,
                ip=contexto.ip,
            )

        if resultado == Resultado.APROBADA:
            tarjeta.cupo_disponible -= solicitud.monto
            tarjeta.save(update_fields=['cupo_disponible', 'fecha_actualizacion'])

        datos = _datos_evento(
            solicitud, comercio, contexto, autorizacion, tarjeta, resultado, motivo, consulta
        )
        registrar_al_confirmar(
            'AUTORIZACION',
            MODULO,
            usuario,
            lambda: {
                **datos,
                'tiempo_respuesta_ms': round((time.perf_counter() - inicio) * 1000),
            },
        )

        if consulta is not None and not consulta.disponible:
            registrar_al_confirmar(
                'MODELO_NO_DISPONIBLE',
                MODULO,
                None,
                {'id_autorizacion': autorizacion.id, 'tiempo_espera_ms': consulta.tiempo_ms},
            )

        if crear_alerta:
            crear_alerta_modelo(autorizacion)

    return Decision(
        id_autorizacion=autorizacion.id if autorizacion else None,
        resultado=resultado,
        motivo_rechazo=motivo,
    )
