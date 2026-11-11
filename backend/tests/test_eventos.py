"""Log de eventos de negocio: catálogo, campos, escritura con on_commit y datos sensibles."""

import logging
import re
import uuid
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from unittest import mock

from rest_framework.test import APIClient

from alertas.models import Alerta
from autorizaciones.models import Autorizacion
from portal.models import Reclamo
from tarjetas.models import Bloqueo
from tests.base import (
    CLAVE,
    CVV,
    PlataformaTestCase,
    capturar_eventos,
    cliente,
    crear_usuario,
)

USER_AGENT_CHROME_WINDOWS = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

CAMPOS_COMUNES = {
    'event_id',
    'event_type',
    'event_time',
    'schema_version',
    'modulo',
    'id_usuario',
    'rol',
}

CAMPOS_AUTORIZACION = {
    'id_autorizacion',
    'id_tarjeta',
    'bin',
    'ultimos_4',
    'id_comercio',
    'categoria',
    'ciudad_comercio',
    'monto',
    'canal',
    'modo_lectura',
    'resultado',
    'motivo_rechazo',
    'probabilidad_fraude',
    'ip',
    'tipo_dispositivo',
    'navegador',
    'sistema_operativo',
    'huella_dispositivo',
    'segundos_formulario',
    'tarjeta_pegada',
    'tiempo_respuesta_ms',
    'tiempo_modelo_ms',
    'version_modelo',
}


class EventoAutorizacionTests(PlataformaTestCase):
    def setUp(self):
        super().setUp()
        # La compra del ejemplo de la especificación es de 1.800.000.
        self.tarjeta.cupo_total = self.tarjeta.cupo_disponible = 5000000
        self.tarjeta.save()

    def comprar_en_linea_registrando(self, **extra):
        with capturar_eventos(self) as eventos:
            self.comprar(
                self.cuerpo_en_linea(1800000, segundos_formulario=2.4, tarjeta_pegada=True),
                HTTP_USER_AGENT=USER_AGENT_CHROME_WINDOWS,
                REMOTE_ADDR='190.24.13.8',
                **extra,
            )
        [evento] = eventos.de_tipo('AUTORIZACION')
        return evento

    def test_trae_los_campos_comunes_y_los_23_propios_de_la_especificacion(self):
        evento = self.comprar_en_linea_registrando()
        self.assertEqual(set(evento) - CAMPOS_COMUNES, CAMPOS_AUTORIZACION)
        self.assertTrue(CAMPOS_COMUNES <= set(evento))

    def test_campos_comunes(self):
        evento = self.comprar_en_linea_registrando()
        uuid.UUID(evento['event_id'])
        self.assertTrue(evento['event_time'].endswith('Z'))
        datetime.strptime(evento['event_time'], '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertEqual(evento['schema_version'], 1)
        self.assertEqual(evento['modulo'], 'autorizador')
        self.assertEqual(evento['id_usuario'], self.comercio.usuario.id)
        self.assertEqual(evento['rol'], 'COMERCIO')

    def test_contexto_de_la_compra_en_linea(self):
        evento = self.comprar_en_linea_registrando()
        self.assertEqual(evento['ip'], '190.24.13.8')
        self.assertEqual(evento['tipo_dispositivo'], 'ESCRITORIO')
        self.assertEqual(evento['navegador'], 'Chrome')
        self.assertEqual(evento['sistema_operativo'], 'Windows')
        self.assertEqual(evento['huella_dispositivo'], 'a91f03c7')
        self.assertEqual(evento['segundos_formulario'], 2.4)
        self.assertIs(evento['tarjeta_pegada'], True)
        self.assertEqual(evento['canal'], 'EN_LINEA')
        self.assertEqual(evento['modo_lectura'], 'DIGITADA')

    def test_datos_de_la_tarjeta_y_del_comercio(self):
        evento = self.comprar_en_linea_registrando()
        autorizacion = Autorizacion.objects.get()
        self.assertEqual(evento['id_autorizacion'], autorizacion.id)
        self.assertEqual(evento['id_tarjeta'], self.tarjeta.id)
        self.assertEqual(evento['bin'], self.tarjeta.numero[:6])
        self.assertEqual(evento['ultimos_4'], self.tarjeta.numero[-4:])
        self.assertEqual(evento['id_comercio'], self.comercio.id)
        self.assertEqual(evento['categoria'], 'ELECTRONICA')
        self.assertEqual(evento['ciudad_comercio'], 'Medellín')
        self.assertEqual(evento['monto'], 1800000)
        self.assertEqual(evento['resultado'], 'APROBADA')
        self.assertIsNone(evento['motivo_rechazo'])

    def test_tiempos_y_version_del_modelo(self):
        evento = self.comprar_en_linea_registrando()
        self.assertIsInstance(evento['tiempo_respuesta_ms'], int)
        self.assertIsInstance(evento['tiempo_modelo_ms'], int)
        self.assertGreaterEqual(evento['tiempo_respuesta_ms'], evento['tiempo_modelo_ms'])
        self.assertTrue(evento['version_modelo'])

    def test_en_presencial_los_campos_de_contexto_van_en_null(self):
        with capturar_eventos(self) as eventos:
            self.comprar(self.cuerpo_presencial(), HTTP_USER_AGENT=USER_AGENT_CHROME_WINDOWS)
        [evento] = eventos.de_tipo('AUTORIZACION')
        for campo in ('huella_dispositivo', 'segundos_formulario', 'tarjeta_pegada'):
            self.assertIn(campo, evento)
            self.assertIsNone(evento[campo], campo)

    def test_rechazada_por_validacion_no_tiene_probabilidad_ni_tiempo_de_modelo(self):
        with capturar_eventos(self) as eventos:
            self.comprar(self.cuerpo_presencial(6000000))  # más que el cupo de 5.000.000
        [evento] = eventos.de_tipo('AUTORIZACION')
        self.assertEqual(evento['motivo_rechazo'], 'CUPO_INSUFICIENTE')
        self.assertIsNone(evento['probabilidad_fraude'])
        self.assertIsNone(evento['tiempo_modelo_ms'])
        self.assertIsNone(evento['version_modelo'])


class EscrituraConOnCommitTests(PlataformaTestCase):
    def test_el_evento_no_se_escribe_hasta_que_la_transaccion_se_confirma(self):
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            with self.assertNoLogs('eventos', level='INFO'):
                self.comprar(self.cuerpo_presencial())
        self.assertEqual(len(pendientes), 1)  # un evento, en espera del commit
        with self.assertLogs('eventos', level='INFO') as registro:
            for devolucion in pendientes:
                devolucion()
        self.assertEqual(len(registro.records), 1)

    def test_si_la_transaccion_falla_no_hay_evento_ni_cupo_descontado(self):
        with mock.patch('autorizaciones.modelo.obtener_probabilidad', return_value=0.9):
            with mock.patch(
                'autorizaciones.servicios.crear_alerta_modelo', side_effect=RuntimeError('falla')
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    with self.assertNoLogs('eventos', level='INFO'):
                        with self.assertRaises(RuntimeError):
                            self.comprar(self.cuerpo_presencial(50000))
        self.assertFalse(Autorizacion.objects.exists())
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.cupo_disponible, 1000000)

    def test_cada_compra_en_linea_genera_un_event_id_distinto(self):
        with capturar_eventos(self) as eventos:
            self.comprar(self.cuerpo_presencial())
            self.comprar(self.cuerpo_presencial())
        ids = [e['event_id'] for e in eventos.eventos]
        self.assertEqual(len(ids), len(set(ids)))


class CatalogoDeEventosTests(PlataformaTestCase):
    """Cada operación de negocio escribe su evento, con los campos de la especificación."""

    def test_alerta_creada_junto_con_la_autorizacion(self):
        with capturar_eventos(self) as eventos:
            with mock.patch('autorizaciones.modelo.obtener_probabilidad', return_value=0.91):
                self.comprar(self.cuerpo_presencial())
        self.assertEqual(eventos.tipos(), ['AUTORIZACION', 'ALERTA_CREADA'])
        [evento] = eventos.de_tipo('ALERTA_CREADA')
        alerta = Alerta.objects.get()
        self.assertEqual(evento['modulo'], 'alertas')
        self.assertEqual(evento['id_alerta'], alerta.id)
        self.assertEqual(evento['tipo'], 'RIESGO_ALTO_MODELO')
        self.assertEqual(evento['id_autorizacion'], alerta.autorizacion_id)
        self.assertEqual(evento['id_tarjeta'], self.tarjeta.id)
        self.assertEqual(evento['id_comercio'], self.comercio.id)
        self.assertAlmostEqual(evento['probabilidad_fraude'], 0.91)

    def crear_alerta(self):
        autorizacion = Autorizacion.objects.create(
            tarjeta=self.tarjeta,
            comercio=self.comercio,
            monto=1000,
            canal='PRESENCIAL',
            modo_lectura='CHIP',
            resultado='APROBADA',
        )
        return Alerta.objects.create(
            tipo='RIESGO_ALTO_MODELO',
            autorizacion=autorizacion,
            tarjeta=self.tarjeta,
            comercio=self.comercio,
            descripcion='Prueba',
        )

    def test_alerta_resuelta(self):
        analista = crear_usuario('ANALISTA')
        alerta = self.crear_alerta()
        with capturar_eventos(self) as eventos:
            cliente(analista).post(
                f'/api/alertas/{alerta.id}/resolver/',
                {'estado': 'CONFIRMADA_FRAUDE'},
                format='json',
            )
        [evento] = eventos.de_tipo('ALERTA_RESUELTA')
        self.assertEqual(evento['modulo'], 'alertas')
        self.assertEqual(evento['id_alerta'], alerta.id)
        self.assertEqual(evento['estado'], 'CONFIRMADA_FRAUDE')
        self.assertEqual(evento['id_usuario'], analista.id)
        self.assertEqual(evento['rol'], 'ANALISTA')

    def test_bloqueo_aplicado_y_levantado_por_el_asociado(self):
        api = cliente(self.asociado.usuario)
        with capturar_eventos(self) as eventos:
            api.post(f'/api/asociado/tarjetas/{self.tarjeta.id}/bloquear/', {}, format='json')
        [evento] = eventos.de_tipo('BLOQUEO_APLICADO')
        bloqueo = Bloqueo.objects.get()
        self.assertEqual(evento['modulo'], 'bloqueos')
        self.assertEqual(evento['id_bloqueo'], bloqueo.id)
        self.assertEqual(evento['tipo'], 'TARJETA')
        self.assertEqual(evento['id_tarjeta'], self.tarjeta.id)
        self.assertIsNone(evento.get('id_comercio'))
        self.assertEqual(evento['origen'], 'ASOCIADO')
        self.assertTrue(evento['motivo'])
        self.assertEqual(evento['rol'], 'ASOCIADO')
        with capturar_eventos(self) as eventos:
            api.post(f'/api/asociado/tarjetas/{self.tarjeta.id}/desbloquear/', {}, format='json')
        [evento] = eventos.de_tipo('BLOQUEO_LEVANTADO')
        self.assertEqual(evento['id_bloqueo'], bloqueo.id)
        self.assertEqual(evento['tipo'], 'TARJETA')
        self.assertEqual(evento['id_tarjeta'], self.tarjeta.id)

    def test_bloqueo_de_comercio_por_el_analista(self):
        analista = crear_usuario('ANALISTA')
        with capturar_eventos(self) as eventos:
            cliente(analista).post(
                '/api/bloqueos/',
                {'tipo': 'COMERCIO', 'comercio': self.comercio.id, 'motivo': 'Sospecha'},
                format='json',
            )
        [evento] = eventos.de_tipo('BLOQUEO_APLICADO')
        self.assertEqual(evento['tipo'], 'COMERCIO')
        self.assertEqual(evento['id_comercio'], self.comercio.id)
        self.assertIsNone(evento.get('id_tarjeta'))
        self.assertEqual(evento['origen'], 'ANALISTA')
        self.assertEqual(evento['rol'], 'ANALISTA')

    def test_reclamo_radicado(self):
        autorizacion = Autorizacion.objects.create(
            tarjeta=self.tarjeta,
            comercio=self.comercio,
            monto=1000,
            canal='PRESENCIAL',
            modo_lectura='CHIP',
            resultado='APROBADA',
        )
        with capturar_eventos(self) as eventos:
            cliente(self.asociado.usuario).post(
                '/api/asociado/reclamos/',
                {'autorizacion': autorizacion.id, 'descripcion': 'No fui yo'},
                format='json',
            )
        [evento] = eventos.de_tipo('RECLAMO_RADICADO')
        self.assertEqual(evento['modulo'], 'portal')
        self.assertEqual(evento['id_reclamo'], Reclamo.objects.get().id)
        self.assertEqual(evento['id_asociado'], self.asociado.id)
        self.assertEqual(evento['id_autorizacion'], autorizacion.id)

    def test_cambio_de_datos_registra_el_campo_pero_no_los_valores(self):
        with capturar_eventos(self) as eventos:
            cliente(self.asociado.usuario).patch(
                '/api/asociado/perfil/',
                {'celular': '3109998877', 'email': 'nuevo.correo@ejemplo.co'},
                format='json',
            )
        cambios = eventos.de_tipo('CAMBIO_DATOS')
        self.assertEqual({e['campo'] for e in cambios}, {'CELULAR', 'EMAIL'})
        for evento in cambios:
            self.assertEqual(evento['modulo'], 'portal')
            self.assertEqual(evento['id_asociado'], self.asociado.id)
        texto = ' '.join(eventos.lineas)
        self.assertNotIn('3109998877', texto)
        self.assertNotIn('nuevo.correo@ejemplo.co', texto)

    def test_perfil_sin_cambios_no_genera_eventos(self):
        with self.assertNoLogs('eventos', level='INFO'):
            with self.captureOnCommitCallbacks(execute=True):
                cliente(self.asociado.usuario).patch(
                    '/api/asociado/perfil/', {'celular': self.asociado.celular}, format='json'
                )

    def test_inicio_de_sesion_exitoso(self):
        with capturar_eventos(self) as eventos:
            APIClient().post(
                '/api/auth/login/',
                {'username': self.asociado.usuario.username, 'password': CLAVE},
                format='json',
                HTTP_USER_AGENT=USER_AGENT_CHROME_WINDOWS,
                REMOTE_ADDR='190.24.13.8',
            )
        [evento] = eventos.de_tipo('INICIO_SESION')
        self.assertEqual(evento['modulo'], 'portal')
        self.assertIs(evento['exitoso'], True)
        self.assertIsNone(evento['motivo_fallo'])
        self.assertEqual(evento['ip'], '190.24.13.8')
        self.assertEqual(evento['navegador'], 'Chrome')
        self.assertEqual(evento['sistema_operativo'], 'Windows')
        self.assertEqual(evento['id_usuario'], self.asociado.usuario.id)

    def test_inicio_de_sesion_fallido_se_registra_con_su_motivo(self):
        with capturar_eventos(self) as eventos:
            APIClient().post(
                '/api/auth/login/',
                {'username': self.asociado.usuario.username, 'password': 'clave-equivocada'},
                format='json',
            )
        [evento] = eventos.de_tipo('INICIO_SESION')
        self.assertIs(evento['exitoso'], False)
        self.assertTrue(evento['motivo_fallo'])


class DatosSensiblesTests(PlataformaTestCase):
    """Nunca se registran el número completo, el CVV, las contraseñas ni valores personales."""

    def test_ninguna_linea_del_log_contiene_datos_sensibles(self):
        cvv = '913'
        clave_mala = 'SuperSecreta!99'
        ajena = '4000001234560002'
        with capturar_eventos(self) as eventos:
            self.comprar(self.cuerpo_en_linea(1000, cvv=cvv))
            self.comprar(self.cuerpo_en_linea(1000, cvv=CVV))
            self.comprar(self.cuerpo_presencial(numero_tarjeta=ajena))
            self.comprar(self.cuerpo_presencial(2000000))
            APIClient().post(
                '/api/auth/login/',
                {'username': self.asociado.usuario.username, 'password': clave_mala},
                format='json',
            )
            cliente(self.asociado.usuario).patch(
                '/api/asociado/perfil/', {'email': 'privado@ejemplo.co'}, format='json'
            )
        texto = '\n'.join(eventos.lineas)
        self.assertGreaterEqual(len(eventos.lineas), 6)
        for secreto in (
            self.tarjeta.numero,
            ajena,
            self.tarjeta.cvv_hash,
            clave_mala,
            CLAVE,
            'privado@ejemplo.co',
        ):
            self.assertNotIn(secreto, texto)
        for evento in eventos.eventos:
            self.assertNotIn('cvv', evento)
            self.assertNotIn('password', evento)
            self.assertNotIn('numero', evento)
            self.assertNotIn('numero_tarjeta', evento)
        self.assertIsNone(re.search(r'\d{13,19}', texto))


class ConfiguracionDelLogTests(PlataformaTestCase):
    def test_archivo_propio_con_rotacion_diaria_y_sin_mezclarse_con_los_logs_tecnicos(self):
        logger = logging.getLogger('eventos')
        rotativos = [h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)]
        self.assertEqual(len(rotativos), 1)
        self.assertEqual(rotativos[0].when, 'MIDNIGHT')
        self.assertEqual(rotativos[0].interval, 24 * 60 * 60)
        self.assertEqual(rotativos[0].formatter._fmt, '%(message)s')
        self.assertFalse(logger.propagate)
