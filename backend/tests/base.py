"""Utilidades compartidas por las pruebas de la plataforma OLTP."""

import calendar
import itertools
import json
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from tarjetas.cvv import hashear_cvv
from tarjetas.models import Tarjeta
from usuarios.models import Asociado, Comercio, Usuario

CLAVE = 'Clave-de-prueba-123'
CVV = '737'

_contador = itertools.count(1)


def crear_usuario(rol, **extra):
    n = next(_contador)
    return Usuario.objects.create_user(
        username=f'{rol.lower()}{n}',
        password=CLAVE,
        email=f'{rol.lower()}{n}@ejemplo.co',
        rol=rol,
        **extra,
    )


def crear_comercio(vende_en_linea=True, **extra):
    n = next(_contador)
    return Comercio.objects.create(
        usuario=crear_usuario('COMERCIO'),
        nombre=f'Comercio {n}',
        nit=f'900{n:06d}-1',
        categoria='ELECTRONICA',
        ciudad='Medellín',
        vende_en_linea=vende_en_linea,
        **extra,
    )


def crear_asociado():
    n = next(_contador)
    return Asociado.objects.create(
        usuario=crear_usuario('ASOCIADO'),
        tipo_documento='CC',
        numero_documento=f'1000{n:06d}',
        nombres='Ana',
        apellidos=f'Pérez {n}',
        fecha_nacimiento=date(1990, 5, 17),
        ciudad='Medellín',
        celular='3001234567',
        email=f'ana{n}@ejemplo.co',
        ingreso_anual=Decimal('48000000'),
        puntaje_crediticio=720,
        fecha_afiliacion=date(2020, 1, 15),
    )


def ultimo_dia(anio, mes):
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def vencimiento_futuro():
    return ultimo_dia(timezone.localdate().year + 2, 12)


def texto_vencimiento(fecha):
    """Formato MM/AA que envía el comercio."""
    return f'{fecha.month:02d}/{fecha.year % 100:02d}'


def crear_tarjeta(
    asociado=None, cupo=Decimal('1000000'), cvv=CVV, numero=None, estado='ACTIVA', vence=None
):
    n = next(_contador)
    numero = numero or f'451234{n:010d}'
    tarjeta = Tarjeta(
        asociado=asociado or crear_asociado(),
        numero=numero,
        franquicia='VISA',
        cvv_hash=hashear_cvv(numero, cvv),
        tiene_chip=True,
        cupo_total=cupo,
        cupo_disponible=cupo,
        fecha_emision=date(2024, 1, 10),
        fecha_vencimiento=vence or vencimiento_futuro(),
        estado=estado,
    )
    tarjeta.save()
    return tarjeta


def cliente(usuario=None):
    api = APIClient()
    if usuario is not None:
        api.force_authenticate(user=usuario)
    return api


class Eventos:
    """Líneas del log de eventos capturadas durante una operación."""

    def __init__(self):
        self.lineas = []

    @property
    def eventos(self):
        return [json.loads(linea) for linea in self.lineas]

    def de_tipo(self, tipo):
        return [e for e in self.eventos if e['event_type'] == tipo]

    def tipos(self):
        return [e['event_type'] for e in self.eventos]


@contextmanager
def capturar_eventos(caso):
    """Captura el log de eventos y ejecuta los `on_commit`, que en TestCase no corren solos."""
    salida = Eventos()
    with caso.assertLogs('eventos', level='INFO') as registro:
        with caso.captureOnCommitCallbacks(execute=True):
            yield salida
    salida.lineas.extend(r.getMessage() for r in registro.records)


class PlataformaTestCase(TestCase):
    """Un comercio que vende en línea y una tarjeta activa con cupo de 1.000.000."""

    def setUp(self):
        self.comercio = crear_comercio(vende_en_linea=True)
        self.tarjeta = crear_tarjeta()
        self.asociado = self.tarjeta.asociado

    def cuerpo_presencial(self, monto=1000, **cambios):
        cuerpo = {
            'numero_tarjeta': self.tarjeta.numero,
            'fecha_vencimiento': texto_vencimiento(self.tarjeta.fecha_vencimiento),
            'monto': str(monto),
            'canal': 'PRESENCIAL',
            'modo_lectura': 'CHIP',
        }
        cuerpo.update(cambios)
        return cuerpo

    def cuerpo_en_linea(self, monto=1000, **cambios):
        cuerpo = self.cuerpo_presencial(monto)
        cuerpo.update(
            {
                'canal': 'EN_LINEA',
                'modo_lectura': 'DIGITADA',
                'cvv': CVV,
                'huella_dispositivo': 'a91f03c7',
                'segundos_formulario': 2.4,
                'tarjeta_pegada': False,
            }
        )
        cuerpo.update(cambios)
        return cuerpo

    def comprar(self, cuerpo, usuario=None, **extra):
        api = cliente(usuario or self.comercio.usuario)
        return api.post('/api/autorizaciones/', cuerpo, format='json', **extra)
