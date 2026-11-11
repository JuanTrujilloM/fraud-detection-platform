"""Log de eventos de negocio: una línea JSON por operación, leída por la ingesta por streaming.

Nunca se registran el número completo de la tarjeta, el CVV, contraseñas ni los valores de los
datos personales que cambian.
"""

import json
import logging
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

logger_eventos = logging.getLogger('eventos')

SCHEMA_VERSION = 1

_NUMERO_DE_TARJETA = re.compile(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)')


def _enmascarar_numeros(texto: str) -> str:
    """Deja solo los últimos 4 dígitos de toda secuencia con el largo de un número de tarjeta."""

    def ocultar(coincidencia: re.Match) -> str:
        digitos = re.sub(r'\D', '', coincidencia.group())
        return '*' * (len(digitos) - 4) + digitos[-4:]

    return _NUMERO_DE_TARJETA.sub(ocultar, texto)


def _serializar(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    raise TypeError(f'Tipo no serializable en un evento: {type(valor).__name__}')


def registrar_evento(event_type: str, modulo: str, usuario, datos: dict[str, Any]) -> None:
    """Escribe el evento de inmediato. Úsese solo fuera de transacciones."""
    evento = {
        'event_id': str(uuid.uuid4()),
        'event_type': event_type,
        'event_time': datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        'schema_version': SCHEMA_VERSION,
        'modulo': modulo,
        'id_usuario': usuario.id if usuario else None,
        'rol': usuario.rol if usuario else None,
    }
    evento.update(
        {c: _enmascarar_numeros(v) if isinstance(v, str) else v for c, v in datos.items()}
    )
    logger_eventos.info(json.dumps(evento, ensure_ascii=False, default=_serializar))


def registrar_al_confirmar(
    event_type: str,
    modulo: str,
    usuario,
    datos: dict[str, Any] | Callable[[], dict[str, Any]],
) -> None:
    """Escribe el evento solo si la transacción en curso se confirma.

    `datos` puede ser una función, para los campos que solo se conocen al confirmar.
    `robust=True` evita que un fallo al escribir el log afecte una operación ya confirmada.
    """

    def escribir() -> None:
        registrar_evento(event_type, modulo, usuario, datos() if callable(datos) else datos)

    transaction.on_commit(escribir, robust=True)
