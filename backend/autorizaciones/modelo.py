"""Acceso al modelo de ML, con tiempo límite. Si no responde, se decide sin él."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

VERSION_MODELO = 'v0-fijo'

# El hilo permite cortar la espera aunque el modelo se quede colgado. No debe tocar la base de
# datos: correría fuera de la transacción de la autorización.
_ejecutor = ThreadPoolExecutor(max_workers=8, thread_name_prefix='modelo')


@dataclass(frozen=True)
class ConsultaModelo:
    disponible: bool
    probabilidad: float | None
    tiempo_ms: int


def obtener_probabilidad(variables: dict[str, Any]) -> float:
    """Probabilidad de fraude de una compra. Mientras no haya modelo entrenado es un valor fijo."""
    return settings.MODELO_PROBABILIDAD_FIJA


def consultar_modelo(variables: dict[str, Any]) -> ConsultaModelo:
    inicio = time.perf_counter()
    limite = settings.TIEMPO_LIMITE_MODELO_MS / 1000
    futuro = _ejecutor.submit(obtener_probabilidad, variables)
    try:
        probabilidad = futuro.result(timeout=limite)
        if not 0 <= probabilidad <= 1:
            raise ValueError(f'Probabilidad fuera de rango: {probabilidad}')
    except TimeoutError:
        futuro.cancel()
        logger.warning('El modelo no respondió en %s ms', settings.TIEMPO_LIMITE_MODELO_MS)
        probabilidad = None
    except Exception:
        # Cualquier fallo del modelo equivale a no disponible: la compra no puede depender de él.
        logger.exception('Falló la consulta al modelo')
        probabilidad = None
    return ConsultaModelo(
        disponible=probabilidad is not None,
        probabilidad=probabilidad,
        tiempo_ms=round((time.perf_counter() - inicio) * 1000),
    )
