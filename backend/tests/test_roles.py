"""Roles y permisos: matriz rol x endpoint, JWT y aislamiento entre usuarios."""

from django.test import TestCase
from rest_framework.test import APIClient

from alertas.models import Alerta
from autorizaciones.models import Autorizacion
from portal.models import Reclamo
from tarjetas.models import Bloqueo, Tarjeta
from tests.base import (
    CLAVE,
    cliente,
    crear_asociado,
    crear_comercio,
    crear_tarjeta,
    crear_usuario,
)
from usuarios.models import Usuario

# (método, ruta, único rol que puede entrar). El ADMIN no tiene acceso a la API: usa /admin/.
ENDPOINTS = [
    ('POST', '/api/autorizaciones/', 'COMERCIO'),
    ('GET', '/api/comercio/autorizaciones/', 'COMERCIO'),
    ('GET', '/api/asociado/tarjetas/', 'ASOCIADO'),
    ('GET', '/api/asociado/tarjetas/{tarjeta}/autorizaciones/', 'ASOCIADO'),
    ('POST', '/api/asociado/tarjetas/{tarjeta}/bloquear/', 'ASOCIADO'),
    ('POST', '/api/asociado/tarjetas/{tarjeta}/desbloquear/', 'ASOCIADO'),
    ('GET', '/api/asociado/reclamos/', 'ASOCIADO'),
    ('POST', '/api/asociado/reclamos/', 'ASOCIADO'),
    ('GET', '/api/asociado/perfil/', 'ASOCIADO'),
    ('PATCH', '/api/asociado/perfil/', 'ASOCIADO'),
    ('GET', '/api/alertas/', 'ANALISTA'),
    ('GET', '/api/alertas/{alerta}/', 'ANALISTA'),
    ('POST', '/api/alertas/{alerta}/resolver/', 'ANALISTA'),
    ('GET', '/api/bloqueos/', 'ANALISTA'),
    ('POST', '/api/bloqueos/', 'ANALISTA'),
    ('POST', '/api/bloqueos/{bloqueo}/levantar/', 'ANALISTA'),
    ('GET', '/api/reclamos/', 'ANALISTA'),
    ('PATCH', '/api/reclamos/{reclamo}/', 'ANALISTA'),
]


class MatrizDeRolesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comercio = crear_comercio()
        cls.asociado = crear_asociado()
        cls.tarjeta = crear_tarjeta(cls.asociado)
        cls.otra_tarjeta = crear_tarjeta()
        cls.analista = crear_usuario('ANALISTA')
        cls.admin = crear_usuario('ADMIN')
        cls.autorizacion = Autorizacion.objects.create(
            tarjeta=cls.tarjeta,
            comercio=cls.comercio,
            monto=1000,
            canal='PRESENCIAL',
            modo_lectura='CHIP',
            resultado='APROBADA',
        )
        cls.alerta = Alerta.objects.create(
            tipo='RIESGO_ALTO_MODELO',
            autorizacion=cls.autorizacion,
            tarjeta=cls.tarjeta,
            comercio=cls.comercio,
            descripcion='Prueba',
        )
        cls.reclamo = Reclamo.objects.create(
            asociado=cls.asociado, autorizacion=cls.autorizacion, descripcion='No fui yo'
        )
        cls.bloqueo = Bloqueo.objects.create(
            tipo='TARJETA',
            tarjeta=cls.otra_tarjeta,
            origen='ANALISTA',
            motivo='Prueba',
            usuario=cls.analista,
        )
        cls.usuarios = {
            'COMERCIO': cls.comercio.usuario,
            'ASOCIADO': cls.asociado.usuario,
            'ANALISTA': cls.analista,
            'ADMIN': cls.admin,
        }

    def ruta(self, plantilla):
        return plantilla.format(
            tarjeta=self.tarjeta.id,
            alerta=self.alerta.id,
            bloqueo=self.bloqueo.id,
            reclamo=self.reclamo.id,
        )

    def test_sin_token_responde_401(self):
        for metodo, plantilla, _ in ENDPOINTS:
            with self.subTest(endpoint=f'{metodo} {plantilla}'):
                respuesta = cliente().generic(
                    metodo, self.ruta(plantilla), '{}', content_type='application/json'
                )
                self.assertEqual(respuesta.status_code, 401)

    def test_un_rol_equivocado_responde_403(self):
        """Cada endpoint rechaza a los otros tres roles, incluido el ADMIN."""
        for metodo, plantilla, permitido in ENDPOINTS:
            for rol, usuario in self.usuarios.items():
                if rol == permitido:
                    continue
                with self.subTest(endpoint=f'{metodo} {plantilla}', rol=rol):
                    respuesta = cliente(usuario).generic(
                        metodo, self.ruta(plantilla), '{}', content_type='application/json'
                    )
                    self.assertEqual(respuesta.status_code, 403)

    def test_el_rol_correcto_lee_con_200(self):
        for metodo, plantilla, permitido in ENDPOINTS:
            if metodo != 'GET':
                continue
            with self.subTest(endpoint=plantilla, rol=permitido):
                respuesta = cliente(self.usuarios[permitido]).get(self.ruta(plantilla))
                self.assertEqual(respuesta.status_code, 200)

    def test_rol_sin_su_ficha_responde_403(self):
        sin_ficha = crear_usuario('ASOCIADO')
        self.assertEqual(cliente(sin_ficha).get('/api/asociado/tarjetas/').status_code, 403)
        sin_ficha = crear_usuario('COMERCIO')
        self.assertEqual(cliente(sin_ficha).get('/api/comercio/autorizaciones/').status_code, 403)
        self.assertEqual(
            cliente(sin_ficha).post('/api/autorizaciones/', {}, format='json').status_code, 403
        )

    def test_ninguna_respuesta_expone_numero_completo_ni_hash_del_cvv(self):
        for metodo, plantilla, permitido in ENDPOINTS:
            if metodo != 'GET':
                continue
            cuerpo = cliente(self.usuarios[permitido]).get(self.ruta(plantilla)).content.decode()
            with self.subTest(endpoint=plantilla):
                for tarjeta in Tarjeta.objects.all():
                    self.assertNotIn(tarjeta.numero, cuerpo)
                    self.assertNotIn(tarjeta.cvv_hash, cuerpo)
                self.assertNotIn('cvv', cuerpo.lower())


class AutenticacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.asociado = crear_asociado()
        cls.usuario = cls.asociado.usuario
        crear_tarjeta(cls.asociado)

    def login(self, username, password=CLAVE):
        return APIClient().post(
            '/api/auth/login/', {'username': username, 'password': password}, format='json'
        )

    def con_token(self, token):
        return APIClient().get('/api/asociado/tarjetas/', HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_login_correcto_entrega_tokens_y_rol(self):
        respuesta = self.login(self.usuario.username)
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertTrue(datos['access'] and datos['refresh'])
        self.assertEqual(datos['usuario']['rol'], 'ASOCIADO')

    def test_clave_incorrecta_responde_401(self):
        self.assertEqual(self.login(self.usuario.username, 'otra-clave').status_code, 401)

    def test_usuario_inexistente_responde_401(self):
        self.assertEqual(self.login('no-existe').status_code, 401)

    def test_usuario_inactivo_no_puede_entrar(self):
        Usuario.objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertEqual(self.login(self.usuario.username).status_code, 401)

    def test_token_de_un_usuario_desactivado_deja_de_servir(self):
        token = self.login(self.usuario.username).json()['access']
        self.assertEqual(self.con_token(token).status_code, 200)
        Usuario.objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertEqual(self.con_token(token).status_code, 401)

    def test_renovar_token_funciona_y_un_usuario_desactivado_no_puede(self):
        refresh = self.login(self.usuario.username).json()['refresh']
        renovado = APIClient().post('/api/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(renovado.status_code, 200)
        self.assertEqual(self.con_token(renovado.json()['access']).status_code, 200)
        Usuario.objects.filter(pk=self.usuario.pk).update(is_active=False)
        again = APIClient().post('/api/auth/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(again.status_code, 401)

    def test_token_basura_responde_401(self):
        self.assertEqual(self.con_token('esto.no.es.un.jwt').status_code, 401)

    def test_el_rol_se_lee_de_la_base_de_datos_no_del_token(self):
        token = self.login(self.usuario.username).json()['access']
        self.assertEqual(self.con_token(token).status_code, 200)
        Usuario.objects.filter(pk=self.usuario.pk).update(rol='ANALISTA')
        self.assertEqual(self.con_token(token).status_code, 403)
        analista = APIClient().get('/api/alertas/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(analista.status_code, 200)


class AislamientoTests(TestCase):
    """Cada asociado y cada comercio ve solo lo suyo."""

    @classmethod
    def setUpTestData(cls):
        cls.comercio_a = crear_comercio()
        cls.comercio_b = crear_comercio()
        cls.tarjeta_a = crear_tarjeta()
        cls.tarjeta_b = crear_tarjeta()
        cls.compra_a = cls.compra(cls.tarjeta_a, cls.comercio_a)
        cls.compra_b = cls.compra(cls.tarjeta_b, cls.comercio_b)

    @staticmethod
    def compra(tarjeta, comercio):
        return Autorizacion.objects.create(
            tarjeta=tarjeta,
            comercio=comercio,
            monto=5000,
            canal='PRESENCIAL',
            modo_lectura='CHIP',
            resultado='APROBADA',
        )

    def test_asociado_solo_lista_sus_tarjetas(self):
        respuesta = cliente(self.tarjeta_a.asociado.usuario).get('/api/asociado/tarjetas/')
        self.assertEqual([t['id'] for t in respuesta.json()], [self.tarjeta_a.id])

    def test_asociado_no_ve_los_movimientos_de_una_tarjeta_ajena(self):
        api = cliente(self.tarjeta_a.asociado.usuario)
        respuesta = api.get(f'/api/asociado/tarjetas/{self.tarjeta_b.id}/autorizaciones/')
        self.assertEqual(respuesta.status_code, 404)

    def test_asociado_no_puede_bloquear_una_tarjeta_ajena(self):
        api = cliente(self.tarjeta_a.asociado.usuario)
        respuesta = api.post(
            f'/api/asociado/tarjetas/{self.tarjeta_b.id}/bloquear/', {}, format='json'
        )
        self.assertEqual(respuesta.status_code, 404)
        self.tarjeta_b.refresh_from_db()
        self.assertEqual(self.tarjeta_b.estado, 'ACTIVA')
        self.assertFalse(Bloqueo.objects.exists())

    def test_asociado_no_puede_reportar_una_compra_ajena(self):
        api = cliente(self.tarjeta_a.asociado.usuario)
        respuesta = api.post(
            '/api/asociado/reclamos/',
            {'autorizacion': self.compra_b.id, 'descripcion': 'No es mía'},
            format='json',
        )
        self.assertNotEqual(respuesta.status_code, 201)
        self.assertFalse(Reclamo.objects.exists())

    def test_asociado_solo_ve_sus_reclamos(self):
        Reclamo.objects.create(
            asociado=self.tarjeta_b.asociado, autorizacion=self.compra_b, descripcion='Del otro'
        )
        respuesta = cliente(self.tarjeta_a.asociado.usuario).get('/api/asociado/reclamos/')
        self.assertEqual(respuesta.json()['count'], 0)

    def test_comercio_solo_ve_su_historial(self):
        respuesta = cliente(self.comercio_a.usuario).get('/api/comercio/autorizaciones/')
        self.assertEqual([a['id'] for a in respuesta.json()['results']], [self.compra_a.id])
