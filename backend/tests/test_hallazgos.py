"""Pruebas de regresión de los hallazgos de la revisión.

Cada una describe el comportamiento CORRECTO. Antes de las correcciones fallaban (14 fallos); hoy
protegen que no vuelvan a aparecer. Los identificadores (B, D, E...) son los del informe.
"""

import re
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib import admin
from django.core.checks import ERROR, run_checks
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings

from alertas.models import Alerta
from eventos.contexto import obtener_ip
from tarjetas.admin import TarjetaAdminForm
from tarjetas.models import Tarjeta
from tests.base import (
    PlataformaTestCase,
    capturar_eventos,
    cliente,
    crear_usuario,
)
from usuarios.models import Comercio, Usuario

NUMERO_COMPLETO = '4512340000009821'


class HallazgoE_DegradarUnAdmin(TestCase):
    """E: cambiar el rol de un ADMIN debe quitarle el acceso al admin de Django."""

    def test_un_admin_degradado_pierde_staff_y_superusuario(self):
        usuario = crear_usuario('ADMIN')
        self.assertTrue(usuario.is_staff and usuario.is_superuser)  # punto de partida
        usuario.rol = 'ANALISTA'
        usuario.save()
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_staff, 'sigue pudiendo entrar a /admin/')
        self.assertFalse(usuario.is_superuser, 'sigue siendo superusuario')

    def test_un_rol_que_no_es_admin_no_puede_tener_permisos_de_admin(self):
        usuario = crear_usuario('ANALISTA')
        usuario.is_superuser = True
        usuario.is_staff = True
        usuario.save()
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_staff or usuario.is_superuser)

    def test_control_un_admin_nuevo_si_recibe_los_permisos(self):
        self.assertTrue(Usuario.objects.create_superuser('root', 'r@e.co', 'x').is_staff)
        self.assertTrue(crear_usuario('ADMIN').is_superuser)


class HallazgoF_CupoDisponibleMayorAlTotal(PlataformaTestCase):
    """F: el cupo disponible nunca puede superar al cupo total."""

    def test_la_base_de_datos_rechaza_un_disponible_mayor_al_total(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tarjeta.objects.filter(pk=self.tarjeta.pk).update(cupo_disponible=2000000)

    def test_el_formulario_del_admin_rechaza_un_disponible_mayor_al_total(self):
        formulario = TarjetaAdminForm(
            data=datos_admin(self.tarjeta, cupo_disponible='2000000'), instance=self.tarjeta
        )
        self.assertFalse(formulario.is_valid())

    def test_control_un_disponible_igual_al_total_es_valido(self):
        formulario = TarjetaAdminForm(data=datos_admin(self.tarjeta), instance=self.tarjeta)
        self.assertTrue(formulario.is_valid(), formulario.errors)


class HallazgoG_CambiarElNumeroSinReescribirElCVV(PlataformaTestCase):
    """G: el número es la sal del hash del CVV; cambiarlo obliga a reingresar el CVV."""

    def test_cambiar_el_numero_sin_cvv_no_es_valido(self):
        datos = datos_admin(self.tarjeta, numero='4512340000001111', cvv='')
        self.assertFalse(TarjetaAdminForm(data=datos, instance=self.tarjeta).is_valid())

    def test_cambiar_el_numero_con_cvv_nuevo_deja_las_compras_en_linea_funcionando(self):
        datos = datos_admin(self.tarjeta, numero='4512340000001111', cvv='555')
        formulario = TarjetaAdminForm(data=datos, instance=self.tarjeta)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()
        cuerpo = self.cuerpo_en_linea(numero_tarjeta='4512340000001111', cvv='555')
        self.assertEqual(self.comprar(cuerpo).json()['resultado'], 'APROBADA')

    def test_control_dejar_el_cvv_vacio_sin_cambiar_el_numero_es_valido(self):
        formulario = TarjetaAdminForm(data=datos_admin(self.tarjeta, cvv=''), instance=self.tarjeta)
        self.assertTrue(formulario.is_valid(), formulario.errors)


class HallazgoH_AdminSinHistorialNiEvento(PlataformaTestCase):
    """H: el bloqueo y las alertas no se editan a mano en el admin (sin historial ni evento).

    La tarjeta sí se puede pasar entre ACTIVA y CANCELADA desde el admin; lo que no se toca es el
    bloqueo, que se aplica y se levanta desde la consola.
    """

    def setUp(self):
        super().setUp()
        self.peticion = RequestFactory().get('/admin/')
        self.peticion.user = crear_usuario('ADMIN')

    def formulario(self, **cambios):
        return TarjetaAdminForm(data=datos_admin(self.tarjeta, **cambios), instance=self.tarjeta)

    def test_el_admin_no_puede_poner_una_tarjeta_en_bloqueada(self):
        self.assertFalse(self.formulario(estado='BLOQUEADA').is_valid())

    def test_el_admin_no_puede_reactivar_una_tarjeta_bloqueada(self):
        self.tarjeta.estado = 'BLOQUEADA'
        self.tarjeta.save()
        formulario = self.formulario(estado='ACTIVA')
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.cleaned_data['estado'], 'BLOQUEADA')
        formulario.save()
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'BLOQUEADA')

    def test_control_el_admin_si_puede_cancelar_una_tarjeta(self):
        formulario = self.formulario(estado='CANCELADA')
        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'CANCELADA')

    def test_el_estado_del_comercio_es_de_solo_lectura(self):
        modelo = admin.site._registry[Comercio]
        self.assertIn('estado', modelo.get_readonly_fields(self.peticion, self.comercio))

    def test_las_alertas_no_se_editan_en_el_admin(self):
        self.assertFalse(admin.site._registry[Alerta].has_change_permission(self.peticion))


class HallazgoJ_LogDeEventosNoEscribible(TestCase):
    """J: si el log no se puede escribir, la app debe avisarlo al arrancar, no perder eventos."""

    def errores(self):
        return [m for m in run_checks() if m.level >= ERROR]

    def test_una_ruta_de_log_que_no_se_puede_escribir_es_un_error_de_configuracion(self):
        carpeta = tempfile.mkdtemp()  # una carpeta no sirve como archivo de log
        with override_settings(EVENTOS_LOG_PATH=Path(carpeta)):
            self.assertTrue(self.errores(), 'la app arranca y perderá todos los eventos')

    def test_control_una_ruta_escribible_no_da_errores(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with override_settings(EVENTOS_LOG_PATH=Path(carpeta) / 'eventos.log'):
                self.assertEqual(self.errores(), [])


class HallazgoK_TextoLibreEnElLog(PlataformaTestCase):
    """K: un número de tarjeta escrito en el motivo de un bloqueo no puede llegar al log."""

    def lineas_de(self, enviar):
        with capturar_eventos(self) as eventos:
            enviar()
        return '\n'.join(eventos.lineas)

    def comprobar(self, texto):
        self.assertNotIn(NUMERO_COMPLETO, texto)
        self.assertIsNone(re.search(r'\d{13,19}', texto))

    def test_motivo_escrito_por_el_asociado(self):
        api = cliente(self.asociado.usuario)
        texto = self.lineas_de(
            lambda: api.post(
                f'/api/asociado/tarjetas/{self.tarjeta.id}/bloquear/',
                {'motivo': f'Me robaron la tarjeta {NUMERO_COMPLETO}, bloquéenla'},
                format='json',
            )
        )
        self.assertIn('BLOQUEO_APLICADO', texto)
        self.comprobar(texto)

    def test_motivo_escrito_por_el_analista(self):
        api = cliente(crear_usuario('ANALISTA'))
        texto = self.lineas_de(
            lambda: api.post(
                '/api/bloqueos/',
                {
                    'tipo': 'TARJETA',
                    'tarjeta': self.tarjeta.id,
                    'motivo': f'Cliente reporta {NUMERO_COMPLETO} clonada',
                },
                format='json',
            )
        )
        self.assertIn('BLOQUEO_APLICADO', texto)
        self.comprobar(texto)

    def test_control_un_motivo_normal_se_conserva(self):
        api = cliente(crear_usuario('ANALISTA'))
        texto = self.lineas_de(
            lambda: api.post(
                '/api/bloqueos/',
                {'tipo': 'TARJETA', 'tarjeta': self.tarjeta.id, 'motivo': 'Compras sospechosas'},
                format='json',
            )
        )
        self.assertIn('Compras sospechosas', texto)


class HallazgoB_IpSinCabeceraDelProxy(TestCase):
    """B: sin X-Forwarded-For (llamada directa al backend) se usa la IP de la conexión."""

    @override_settings(NUM_PROXIES=1)
    def test_sin_cabecera_usa_remote_addr(self):
        peticion = RequestFactory().get('/', REMOTE_ADDR='172.18.0.1')
        self.assertEqual(obtener_ip(peticion), '172.18.0.1')

    @override_settings(NUM_PROXIES=1)
    def test_cabecera_vacia_usa_remote_addr(self):
        peticion = RequestFactory().get('/', REMOTE_ADDR='172.18.0.1', HTTP_X_FORWARDED_FOR='')
        self.assertEqual(obtener_ip(peticion), '172.18.0.1')


class HallazgoD_VersionDelModeloSinRespuesta(PlataformaTestCase):
    """D: si el modelo no respondió, el evento no debe declarar la versión de un modelo."""

    def test_version_modelo_es_null_si_el_modelo_no_estuvo_disponible(self):
        with capturar_eventos(self) as eventos:
            with mock.patch('autorizaciones.modelo.obtener_probabilidad', side_effect=RuntimeError):
                self.comprar(self.cuerpo_presencial())
        [evento] = eventos.de_tipo('AUTORIZACION')
        self.assertIsNone(evento['probabilidad_fraude'])
        self.assertIsNone(evento['version_modelo'])

    def test_control_con_el_modelo_disponible_se_informa_la_version(self):
        with capturar_eventos(self) as eventos:
            self.comprar(self.cuerpo_presencial())
        self.assertTrue(eventos.de_tipo('AUTORIZACION')[0]['version_modelo'])


def datos_admin(tarjeta, **cambios):
    """Datos del formulario de tarjeta del admin, tal como los enviaría el navegador."""
    datos = {
        'asociado': tarjeta.asociado_id,
        'numero': tarjeta.numero,
        'cvv': '',
        'franquicia': tarjeta.franquicia,
        'fecha_vencimiento': tarjeta.fecha_vencimiento,
        'tiene_chip': 'on',
        'cupo_total': str(tarjeta.cupo_total),
        'cupo_disponible': str(tarjeta.cupo_disponible),
        'fecha_emision': tarjeta.fecha_emision,
        'estado': tarjeta.estado,
    }
    datos.update(cambios)
    return datos
