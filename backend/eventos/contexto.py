"""Contexto de la petición que acompaña a los eventos: IP y datos del user agent."""

import ipaddress
from dataclasses import dataclass

from django.conf import settings
from user_agents import parse


@dataclass(frozen=True)
class ContextoPeticion:
    ip: str | None
    tipo_dispositivo: str
    navegador: str | None
    sistema_operativo: str | None


def obtener_ip(request) -> str | None:
    """IP del cliente. Solo confía en los saltos de X-Forwarded-For que agregaron nuestros proxies.

    Las entradas de la izquierda las puede enviar cualquier cliente, así que se cuenta desde la
    derecha: con NUM_PROXIES=1, la IP real es la última.
    """
    ip = request.META.get('REMOTE_ADDR')
    cabecera = request.META.get('HTTP_X_FORWARDED_FOR', '').strip()
    if settings.NUM_PROXIES > 0 and cabecera:
        saltos = [s.strip() for s in cabecera.split(',')]
        if len(saltos) >= settings.NUM_PROXIES:
            ip = saltos[-settings.NUM_PROXIES]
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return None
    # Algunos proxies escriben las IPv4 como ::ffff:a.b.c.d; en el log deben verse siempre igual.
    mapeada = getattr(direccion, 'ipv4_mapped', None)
    return str(mapeada or direccion)


def _tipo_dispositivo(agente) -> str:
    if agente.is_tablet:
        return 'TABLET'
    if agente.is_mobile:
        return 'MOVIL'
    if agente.is_pc:
        return 'ESCRITORIO'
    return 'OTRO'


def obtener_contexto(request) -> ContextoPeticion:
    cadena = request.META.get('HTTP_USER_AGENT', '')
    agente = parse(cadena)
    return ContextoPeticion(
        ip=obtener_ip(request),
        tipo_dispositivo=_tipo_dispositivo(agente),
        navegador=agente.browser.family if cadena else None,
        sistema_operativo=agente.os.family if cadena else None,
    )
