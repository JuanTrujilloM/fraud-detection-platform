"""Concurrencia: compras simultáneas no pueden sobrepasar el cupo.

Usa TransactionTestCase porque necesita transacciones reales (con `TestCase` todo corre dentro de
una sola transacción y `select_for_update` no se podría ejercitar entre hilos).
"""

import threading
import time
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase

from autorizaciones.models import Autorizacion
from tests.base import (
    cliente,
    crear_comercio,
    crear_tarjeta,
    texto_vencimiento,
)


class ComprasSimultaneasTests(TransactionTestCase):
    def setUp(self):
        self.comercio = crear_comercio()
        self.tarjeta = crear_tarjeta(cupo=Decimal('100000'))

    def cuerpo(self, monto):
        return {
            'numero_tarjeta': self.tarjeta.numero,
            'fecha_vencimiento': texto_vencimiento(self.tarjeta.fecha_vencimiento),
            'monto': str(monto),
            'canal': 'PRESENCIAL',
            'modo_lectura': 'CHIP',
        }

    def comprar_en_paralelo(self, montos):
        """Lanza todas las compras a la vez. El modelo tarda 100 ms para que se solapen."""
        barrera = threading.Barrier(len(montos))
        resultados = [None] * len(montos)

        def trabajo(posicion, monto):
            try:
                barrera.wait(timeout=10)
                respuesta = cliente(self.comercio.usuario).post(
                    '/api/autorizaciones/', self.cuerpo(monto), format='json'
                )
                resultados[posicion] = respuesta.json()
            except Exception as error:  # se reporta en el hilo principal
                resultados[posicion] = {'error': repr(error)}
            finally:
                connection.close()

        def modelo_lento(variables):
            time.sleep(0.1)
            return 0.01

        with mock.patch('autorizaciones.modelo.obtener_probabilidad', side_effect=modelo_lento):
            hilos = [
                threading.Thread(target=trabajo, args=(i, monto)) for i, monto in enumerate(montos)
            ]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=60)
        for resultado in resultados:
            self.assertNotIn('error', resultado or {}, resultado)
        return resultados

    def test_dos_compras_que_juntas_pasan_del_cupo_solo_aprueban_una(self):
        resultados = self.comprar_en_paralelo([60000, 60000])
        aprobadas = [r for r in resultados if r['resultado'] == 'APROBADA']
        rechazadas = [r for r in resultados if r['resultado'] == 'RECHAZADA']
        self.assertEqual(len(aprobadas), 1, resultados)
        self.assertEqual(len(rechazadas), 1, resultados)
        self.assertEqual(rechazadas[0]['motivo_rechazo'], 'CUPO_INSUFICIENTE')
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.cupo_disponible, Decimal('40000'))

    def test_ocho_compras_simultaneas_aprueban_exactamente_las_que_caben(self):
        resultados = self.comprar_en_paralelo([30000] * 8)
        aprobadas = [r for r in resultados if r['resultado'] == 'APROBADA']
        self.assertEqual(len(aprobadas), 3, resultados)  # 3 x 30.000 = 90.000 de 100.000
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.cupo_disponible, Decimal('10000'))
        self.assertGreaterEqual(self.tarjeta.cupo_disponible, 0)

    def test_el_cupo_descontado_coincide_con_lo_aprobado_en_la_base(self):
        self.comprar_en_paralelo([30000] * 6)
        aprobado = sum(a.monto for a in Autorizacion.objects.filter(resultado='APROBADA'))
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.cupo_total - self.tarjeta.cupo_disponible, aprobado)
        self.assertEqual(Autorizacion.objects.count(), 6)  # aprobadas y rechazadas se guardan
