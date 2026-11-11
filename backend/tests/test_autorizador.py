"""Autorizador: las 8 validaciones y su orden, los umbrales del modelo y el modelo caído."""

import time
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from alertas.models import Alerta
from autorizaciones.models import Autorizacion
from tests.base import (
    PlataformaTestCase,
    capturar_eventos,
    crear_comercio,
    crear_tarjeta,
    texto_vencimiento,
    ultimo_dia,
)


def modelo_devuelve(valor):
    return mock.patch('autorizaciones.modelo.obtener_probabilidad', return_value=valor)


class AutorizadorBase(PlataformaTestCase):
    def assertDecision(self, respuesta, resultado, motivo=None):
        self.assertIn(respuesta.status_code, (200, 201), respuesta.content)
        datos = respuesta.json()
        self.assertEqual(datos['resultado'], resultado, datos)
        self.assertEqual(datos['motivo_rechazo'], motivo, datos)
        return datos

    def cupo(self):
        self.tarjeta.refresh_from_db()
        return self.tarjeta.cupo_disponible


class CompraAprobadaTests(AutorizadorBase):
    def test_compra_presencial_aprobada_descuenta_el_cupo(self):
        datos = self.assertDecision(self.comprar(self.cuerpo_presencial(250000)), 'APROBADA')
        self.assertIsNotNone(datos['id_autorizacion'])
        self.assertEqual(self.cupo(), Decimal('750000'))
        autorizacion = Autorizacion.objects.get()
        self.assertEqual(autorizacion.id, datos['id_autorizacion'])
        self.assertEqual(autorizacion.resultado, 'APROBADA')

    def test_sin_pin_chip_y_banda_no_validan_nada_adicional(self):
        for modo in ('CHIP', 'BANDA'):
            with self.subTest(modo=modo):
                cuerpo = self.cuerpo_presencial(1000, modo_lectura=modo)
                self.assertDecision(self.comprar(cuerpo), 'APROBADA')

    def test_compra_en_linea_aprobada(self):
        self.assertDecision(self.comprar(self.cuerpo_en_linea(80000)), 'APROBADA')
        self.assertEqual(self.cupo(), Decimal('920000'))

    def test_un_monto_igual_al_cupo_disponible_se_aprueba(self):
        self.assertDecision(self.comprar(self.cuerpo_presencial(1000000)), 'APROBADA')
        self.assertEqual(self.cupo(), Decimal('0'))

    def test_la_tarjeta_vale_hasta_el_ultimo_dia_de_su_mes_de_vencimiento(self):
        hoy = timezone.localdate()
        tarjeta = crear_tarjeta(vence=ultimo_dia(hoy.year, hoy.month))
        cuerpo = {
            'numero_tarjeta': tarjeta.numero,
            'fecha_vencimiento': texto_vencimiento(tarjeta.fecha_vencimiento),
            'monto': '1000',
            'canal': 'PRESENCIAL',
            'modo_lectura': 'CHIP',
        }
        self.assertDecision(self.comprar(cuerpo), 'APROBADA')


class ValidacionesTests(AutorizadorBase):
    """Cada validación por separado, con el motivo exacto de la especificación."""

    def rechazada(self, respuesta, motivo):
        return self.assertDecision(respuesta, 'RECHAZADA', motivo)

    def test_1_comercio_bloqueado(self):
        self.comercio.estado = 'BLOQUEADO'
        self.comercio.save()
        self.rechazada(self.comprar(self.cuerpo_presencial()), 'COMERCIO_BLOQUEADO')

    def test_2_canal_no_permitido_si_el_comercio_no_vende_en_linea(self):
        self.comercio.vende_en_linea = False
        self.comercio.save()
        self.rechazada(self.comprar(self.cuerpo_en_linea()), 'CANAL_NO_PERMITIDO')

    def test_2_el_comercio_sin_venta_en_linea_si_puede_cobrar_presencial(self):
        self.comercio.vende_en_linea = False
        self.comercio.save()
        self.assertDecision(self.comprar(self.cuerpo_presencial()), 'APROBADA')

    def test_3_tarjeta_inexistente_no_se_guarda_y_no_tiene_id(self):
        cuerpo = self.cuerpo_presencial(numero_tarjeta='4000000000000002')
        datos = self.rechazada(self.comprar(cuerpo), 'TARJETA_INEXISTENTE')
        self.assertIsNone(datos['id_autorizacion'])
        self.assertFalse(Autorizacion.objects.exists())

    def test_4_tarjeta_bloqueada(self):
        self.tarjeta.estado = 'BLOQUEADA'
        self.tarjeta.save()
        self.rechazada(self.comprar(self.cuerpo_presencial()), 'TARJETA_BLOQUEADA')

    def test_4_tarjeta_cancelada(self):
        self.tarjeta.estado = 'CANCELADA'
        self.tarjeta.save()
        self.rechazada(self.comprar(self.cuerpo_presencial()), 'TARJETA_CANCELADA')

    def test_5_fecha_de_vencimiento_que_no_coincide(self):
        cuerpo = self.cuerpo_presencial(fecha_vencimiento='01/99')
        self.rechazada(self.comprar(cuerpo), 'DATOS_INVALIDOS')

    def test_5_tarjeta_vencida(self):
        tarjeta = crear_tarjeta(vence=date(2020, 1, 31))
        cuerpo = self.cuerpo_presencial(numero_tarjeta=tarjeta.numero, fecha_vencimiento='01/20')
        self.rechazada(self.comprar(cuerpo), 'TARJETA_VENCIDA')

    def test_6_cvv_invalido_solo_en_linea(self):
        self.rechazada(self.comprar(self.cuerpo_en_linea(cvv='000')), 'CVV_INVALIDO')

    def test_6_presencial_no_pide_cvv(self):
        self.assertNotIn('cvv', self.cuerpo_presencial())
        self.assertDecision(self.comprar(self.cuerpo_presencial()), 'APROBADA')

    def test_7_cupo_insuficiente(self):
        self.rechazada(self.comprar(self.cuerpo_presencial(1000001)), 'CUPO_INSUFICIENTE')

    def test_8_riesgo_alto(self):
        with modelo_devuelve(0.95):
            self.rechazada(self.comprar(self.cuerpo_presencial()), 'RIESGO_ALTO')

    def test_un_rechazo_no_descuenta_cupo_y_se_guarda_con_su_motivo(self):
        self.tarjeta.estado = 'BLOQUEADA'
        self.tarjeta.save()
        self.comprar(self.cuerpo_presencial(5000))
        self.assertEqual(self.cupo(), Decimal('1000000'))
        autorizacion = Autorizacion.objects.get()
        self.assertEqual(autorizacion.resultado, 'RECHAZADA')
        self.assertEqual(autorizacion.motivo_rechazo, 'TARJETA_BLOQUEADA')


class OrdenDeValidacionesTests(AutorizadorBase):
    """Se rechaza en la primera validación que falla: de la más barata a la más costosa."""

    def motivo(self, cuerpo):
        return self.comprar(cuerpo).json()['motivo_rechazo']

    def test_1_antes_que_3_comercio_bloqueado_y_tarjeta_inexistente(self):
        self.comercio.estado = 'BLOQUEADO'
        self.comercio.save()
        cuerpo = self.cuerpo_presencial(numero_tarjeta='4000000000000002')
        self.assertEqual(self.motivo(cuerpo), 'COMERCIO_BLOQUEADO')

    def test_2_antes_que_4_canal_no_permitido_y_tarjeta_bloqueada(self):
        self.comercio.vende_en_linea = False
        self.comercio.save()
        self.tarjeta.estado = 'BLOQUEADA'
        self.tarjeta.save()
        self.assertEqual(self.motivo(self.cuerpo_en_linea()), 'CANAL_NO_PERMITIDO')

    def test_4_antes_que_5_tarjeta_bloqueada_y_fecha_mala(self):
        self.tarjeta.estado = 'BLOQUEADA'
        self.tarjeta.save()
        cuerpo = self.cuerpo_presencial(fecha_vencimiento='01/99')
        self.assertEqual(self.motivo(cuerpo), 'TARJETA_BLOQUEADA')

    def test_5_antes_que_6_fecha_mala_y_cvv_malo(self):
        cuerpo = self.cuerpo_en_linea(fecha_vencimiento='01/99', cvv='000')
        self.assertEqual(self.motivo(cuerpo), 'DATOS_INVALIDOS')

    def test_6_antes_que_7_cvv_malo_y_cupo_insuficiente(self):
        cuerpo = self.cuerpo_en_linea(2000000, cvv='000')
        self.assertEqual(self.motivo(cuerpo), 'CVV_INVALIDO')

    def test_7_antes_que_8_cupo_insuficiente_y_riesgo_alto(self):
        with modelo_devuelve(0.99):
            self.assertEqual(self.motivo(self.cuerpo_presencial(2000000)), 'CUPO_INSUFICIENTE')

    def test_el_modelo_no_se_consulta_si_falla_una_validacion_anterior(self):
        """El modelo es lo más costoso: solo se llama si las validaciones 1 a 7 pasaron."""
        casos = {
            'cupo': self.cuerpo_presencial(2000000),
            'cvv': self.cuerpo_en_linea(cvv='000'),
            'fecha': self.cuerpo_presencial(fecha_vencimiento='01/99'),
            'tarjeta inexistente': self.cuerpo_presencial(numero_tarjeta='4000000000000002'),
        }
        with modelo_devuelve(0.1) as modelo:
            for nombre, cuerpo in casos.items():
                with self.subTest(caso=nombre):
                    self.comprar(cuerpo)
            self.assertEqual(modelo.call_count, 0)

    def test_el_modelo_se_consulta_una_vez_si_pasan_las_validaciones(self):
        with modelo_devuelve(0.1) as modelo:
            self.comprar(self.cuerpo_presencial())
            self.assertEqual(modelo.call_count, 1)


class EntradaTests(AutorizadorBase):
    def test_en_linea_exige_los_campos_de_contexto(self):
        for campo in ('cvv', 'huella_dispositivo', 'segundos_formulario', 'tarjeta_pegada'):
            with self.subTest(campo=campo):
                cuerpo = self.cuerpo_en_linea()
                del cuerpo[campo]
                respuesta = self.comprar(cuerpo)
                self.assertEqual(respuesta.status_code, 400)

    def test_monto_cero_o_negativo_responde_400(self):
        for monto in ('0', '-5000'):
            with self.subTest(monto=monto):
                self.assertEqual(self.comprar(self.cuerpo_presencial(monto)).status_code, 400)

    def test_numero_con_letras_responde_400(self):
        cuerpo = self.cuerpo_presencial(numero_tarjeta='4512ABCD00009821')
        self.assertEqual(self.comprar(cuerpo).status_code, 400)

    def test_los_errores_400_no_repiten_el_numero_ni_el_cvv(self):
        cuerpo = self.cuerpo_en_linea(numero_tarjeta='4512ABCD00009821', cvv='9x')
        respuesta = self.comprar(cuerpo)
        self.assertEqual(respuesta.status_code, 400)
        texto = respuesta.content.decode()
        self.assertNotIn('4512ABCD00009821', texto)
        self.assertNotIn('9x', texto)

    def test_una_peticion_invalida_no_guarda_nada(self):
        self.comprar(self.cuerpo_presencial('0'))
        self.assertFalse(Autorizacion.objects.exists())


class UmbralesDelModeloTests(AutorizadorBase):
    def comprar_con(self, probabilidad, monto=100000):
        with modelo_devuelve(probabilidad):
            return self.comprar(self.cuerpo_presencial(monto))

    def test_probabilidad_en_el_umbral_de_rechazo_rechaza_y_crea_alerta(self):
        self.assertDecision(self.comprar_con(0.85), 'RECHAZADA', 'RIESGO_ALTO')
        alerta = Alerta.objects.get()
        self.assertEqual(alerta.tipo, 'RIESGO_ALTO_MODELO')
        self.assertEqual(alerta.estado, 'PENDIENTE')
        self.assertEqual(alerta.autorizacion_id, Autorizacion.objects.get().id)
        self.assertEqual(self.cupo(), Decimal('1000000'))

    def test_justo_debajo_del_umbral_de_rechazo_aprueba_con_alerta(self):
        self.assertDecision(self.comprar_con(0.8499), 'APROBADA')
        self.assertEqual(Alerta.objects.count(), 1)
        self.assertEqual(self.cupo(), Decimal('900000'))

    def test_probabilidad_en_el_umbral_de_alerta_aprueba_con_alerta(self):
        self.assertDecision(self.comprar_con(0.60), 'APROBADA')
        self.assertEqual(Alerta.objects.count(), 1)

    def test_justo_debajo_del_umbral_de_alerta_aprueba_sin_alerta(self):
        self.assertDecision(self.comprar_con(0.5999), 'APROBADA')
        self.assertEqual(Alerta.objects.count(), 0)

    def test_probabilidad_cero_aprueba_sin_alerta(self):
        self.assertDecision(self.comprar_con(0.0), 'APROBADA')
        self.assertEqual(Alerta.objects.count(), 0)

    def test_la_tarjeta_nunca_se_bloquea_sola(self):
        self.comprar_con(0.99)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'ACTIVA')

    def test_se_guarda_la_probabilidad_del_modelo(self):
        self.comprar_con(0.42)
        self.assertAlmostEqual(Autorizacion.objects.get().probabilidad_fraude, 0.42)

    def test_los_umbrales_se_leen_de_la_configuracion(self):
        with override_settings(UMBRAL_RECHAZO_MODELO=0.5, UMBRAL_ALERTA_MODELO=0.3):
            self.assertDecision(self.comprar_con(0.55), 'RECHAZADA', 'RIESGO_ALTO')
            self.assertDecision(self.comprar_con(0.35), 'APROBADA')
            self.assertEqual(Alerta.objects.count(), 2)


class ModeloNoDisponibleTests(AutorizadorBase):
    """Si el modelo no responde, se decide con las validaciones 1 a 7."""

    def comprar_con_modelo_caido(self, **parche):
        with capturar_eventos(self) as eventos:
            with mock.patch('autorizaciones.modelo.obtener_probabilidad', **parche):
                respuesta = self.comprar(self.cuerpo_presencial(100000))
        return respuesta, eventos

    def verificar_aprobada_sin_modelo(self, respuesta, eventos):
        self.assertDecision(respuesta, 'APROBADA')
        autorizacion = Autorizacion.objects.get()
        self.assertIsNone(autorizacion.probabilidad_fraude)
        self.assertEqual(Alerta.objects.count(), 0)
        aviso = eventos.de_tipo('MODELO_NO_DISPONIBLE')
        self.assertEqual(len(aviso), 1, eventos.tipos())
        self.assertEqual(aviso[0]['id_autorizacion'], autorizacion.id)
        self.assertIn('tiempo_espera_ms', aviso[0])
        return aviso[0]

    def test_modelo_lento_se_corta_al_tiempo_limite(self):
        def lento(variables):
            time.sleep(0.4)
            return 0.05

        with override_settings(TIEMPO_LIMITE_MODELO_MS=100):
            respuesta, eventos = self.comprar_con_modelo_caido(side_effect=lento)
        aviso = self.verificar_aprobada_sin_modelo(respuesta, eventos)
        self.assertGreaterEqual(aviso['tiempo_espera_ms'], 100)
        compra = eventos.de_tipo('AUTORIZACION')[0]
        self.assertLess(compra['tiempo_respuesta_ms'], 350)

    def test_modelo_que_lanza_excepcion(self):
        respuesta, eventos = self.comprar_con_modelo_caido(side_effect=RuntimeError('caído'))
        self.verificar_aprobada_sin_modelo(respuesta, eventos)

    def test_modelo_que_devuelve_una_probabilidad_fuera_de_rango(self):
        respuesta, eventos = self.comprar_con_modelo_caido(return_value=1.5)
        self.verificar_aprobada_sin_modelo(respuesta, eventos)

    def test_sin_modelo_las_validaciones_siguen_rechazando(self):
        with mock.patch('autorizaciones.modelo.obtener_probabilidad', side_effect=RuntimeError):
            respuesta = self.comprar(self.cuerpo_presencial(2000000))
        self.assertDecision(respuesta, 'RECHAZADA', 'CUPO_INSUFICIENTE')

    def test_si_el_modelo_no_se_consulta_no_hay_evento_de_modelo_caido(self):
        with capturar_eventos(self) as eventos:
            self.comprar(self.cuerpo_presencial(2000000))
        self.assertEqual(eventos.de_tipo('MODELO_NO_DISPONIBLE'), [])


class TarjetaInexistenteTests(AutorizadorBase):
    def test_solo_queda_en_el_log_con_bin_y_ultimos_4(self):
        cuerpo = self.cuerpo_presencial(numero_tarjeta='4000001234560002')
        with capturar_eventos(self) as eventos:
            self.comprar(cuerpo)
        self.assertFalse(Autorizacion.objects.exists())
        [evento] = eventos.de_tipo('AUTORIZACION')
        self.assertIsNone(evento['id_autorizacion'])
        self.assertIsNone(evento['id_tarjeta'])
        self.assertEqual(evento['bin'], '400000')
        self.assertEqual(evento['ultimos_4'], '0002')
        self.assertEqual(evento['resultado'], 'RECHAZADA')
        self.assertEqual(evento['motivo_rechazo'], 'TARJETA_INEXISTENTE')
        self.assertNotIn('4000001234560002', eventos.lineas[0])


class UnComercioNoPuedeActuarPorOtroTests(AutorizadorBase):
    def test_la_autorizacion_queda_a_nombre_del_comercio_autenticado(self):
        otro = crear_comercio()
        self.comprar(self.cuerpo_presencial(), usuario=otro.usuario)
        self.assertEqual(Autorizacion.objects.get().comercio_id, otro.id)
