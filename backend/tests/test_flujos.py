"""Flujos de negocio de asociado y analista: bloqueos, alertas, reclamos y perfil."""

from datetime import UTC, datetime

from django.db import IntegrityError, transaction

from alertas.models import Alerta
from autorizaciones.models import Autorizacion
from portal.models import Reclamo
from tarjetas.models import Bloqueo
from tests.base import PlataformaTestCase, cliente, crear_usuario


def crear_compra(tarjeta, comercio, monto=1000, resultado='APROBADA'):
    return Autorizacion.objects.create(
        tarjeta=tarjeta,
        comercio=comercio,
        monto=monto,
        canal='PRESENCIAL',
        modo_lectura='CHIP',
        resultado=resultado,
    )


class BloqueoDelAsociadoTests(PlataformaTestCase):
    def setUp(self):
        super().setUp()
        self.api = cliente(self.asociado.usuario)
        self.url_bloquear = f'/api/asociado/tarjetas/{self.tarjeta.id}/bloquear/'
        self.url_desbloquear = f'/api/asociado/tarjetas/{self.tarjeta.id}/desbloquear/'

    def estado(self):
        self.tarjeta.refresh_from_db()
        return self.tarjeta.estado

    def test_bloquear_deja_la_tarjeta_bloqueada_y_registra_el_bloqueo(self):
        self.assertEqual(self.api.post(self.url_bloquear, {}, format='json').status_code, 201)
        self.assertEqual(self.estado(), 'BLOQUEADA')
        bloqueo = Bloqueo.objects.get()
        self.assertEqual(bloqueo.tipo, 'TARJETA')
        self.assertEqual(bloqueo.origen, 'ASOCIADO')
        self.assertEqual(bloqueo.usuario_id, self.asociado.usuario.id)
        self.assertIsNone(bloqueo.fecha_fin)

    def test_una_tarjeta_bloqueada_rechaza_las_compras(self):
        self.api.post(self.url_bloquear, {}, format='json')
        respuesta = self.comprar(self.cuerpo_presencial())
        self.assertEqual(respuesta.json()['motivo_rechazo'], 'TARJETA_BLOQUEADA')

    def test_bloquear_dos_veces_responde_409(self):
        self.api.post(self.url_bloquear, {}, format='json')
        self.assertEqual(self.api.post(self.url_bloquear, {}, format='json').status_code, 409)
        self.assertEqual(Bloqueo.objects.count(), 1)

    def test_una_tarjeta_cancelada_no_se_puede_bloquear(self):
        self.tarjeta.estado = 'CANCELADA'
        self.tarjeta.save()
        self.assertEqual(self.api.post(self.url_bloquear, {}, format='json').status_code, 409)
        self.assertEqual(self.estado(), 'CANCELADA')

    def test_el_asociado_levanta_su_propio_bloqueo(self):
        self.api.post(self.url_bloquear, {}, format='json')
        tarjetas = self.api.get('/api/asociado/tarjetas/').json()
        self.assertTrue(tarjetas[0]['puede_desbloquear'])
        self.assertEqual(self.api.post(self.url_desbloquear, {}, format='json').status_code, 200)
        self.assertEqual(self.estado(), 'ACTIVA')
        self.assertIsNotNone(Bloqueo.objects.get().fecha_fin)
        self.assertEqual(self.comprar(self.cuerpo_presencial()).json()['resultado'], 'APROBADA')

    def test_el_asociado_no_levanta_un_bloqueo_puesto_por_el_analista(self):
        analista = crear_usuario('ANALISTA')
        cliente(analista).post(
            '/api/bloqueos/',
            {'tipo': 'TARJETA', 'tarjeta': self.tarjeta.id, 'motivo': 'Sospecha de fraude'},
            format='json',
        )
        tarjetas = self.api.get('/api/asociado/tarjetas/').json()
        self.assertEqual(tarjetas[0]['estado'], 'BLOQUEADA')
        self.assertFalse(tarjetas[0]['puede_desbloquear'])
        self.assertEqual(self.api.post(self.url_desbloquear, {}, format='json').status_code, 403)
        self.assertEqual(self.estado(), 'BLOQUEADA')
        self.assertIsNone(Bloqueo.objects.get().fecha_fin)

    def test_desbloquear_una_tarjeta_sin_bloqueo_vigente_falla(self):
        respuesta = self.api.post(self.url_desbloquear, {}, format='json')
        self.assertIn(respuesta.status_code, (400, 409))
        self.assertEqual(self.estado(), 'ACTIVA')


class BloqueoDelAnalistaTests(PlataformaTestCase):
    def setUp(self):
        super().setUp()
        self.analista = crear_usuario('ANALISTA')
        self.api = cliente(self.analista)

    def bloquear(self, **datos):
        datos.setdefault('motivo', 'Sospecha de fraude')
        return self.api.post('/api/bloqueos/', datos, format='json')

    def test_bloquear_una_tarjeta(self):
        respuesta = self.bloquear(tipo='TARJETA', tarjeta=self.tarjeta.id)
        self.assertEqual(respuesta.status_code, 201)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'BLOQUEADA')
        bloqueo = Bloqueo.objects.get()
        self.assertEqual(bloqueo.origen, 'ANALISTA')
        self.assertEqual(bloqueo.usuario_id, self.analista.id)

    def test_bloquear_un_comercio_impide_que_cobre_y_levantarlo_lo_reactiva(self):
        respuesta = self.bloquear(tipo='COMERCIO', comercio=self.comercio.id)
        self.assertEqual(respuesta.status_code, 201)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.estado, 'BLOQUEADO')
        rechazo = self.comprar(self.cuerpo_presencial()).json()
        self.assertEqual(rechazo['motivo_rechazo'], 'COMERCIO_BLOQUEADO')
        levantar = self.api.post(f'/api/bloqueos/{respuesta.json()["id"]}/levantar/')
        self.assertEqual(levantar.status_code, 200)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.estado, 'ACTIVO')
        self.assertEqual(self.comprar(self.cuerpo_presencial()).json()['resultado'], 'APROBADA')

    def test_levantar_un_bloqueo_de_tarjeta_y_no_se_puede_levantar_dos_veces(self):
        bloqueo_id = self.bloquear(tipo='TARJETA', tarjeta=self.tarjeta.id).json()['id']
        url = f'/api/bloqueos/{bloqueo_id}/levantar/'
        self.assertEqual(self.api.post(url).status_code, 200)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'ACTIVA')
        self.assertIn(self.api.post(url).status_code, (400, 409))

    def test_bloquear_lo_ya_bloqueado_responde_409(self):
        self.bloquear(tipo='TARJETA', tarjeta=self.tarjeta.id)
        self.assertEqual(self.bloquear(tipo='TARJETA', tarjeta=self.tarjeta.id).status_code, 409)
        self.assertEqual(Bloqueo.objects.count(), 1)

    def test_el_analista_puede_levantar_el_bloqueo_que_puso_el_asociado(self):
        cliente(self.asociado.usuario).post(
            f'/api/asociado/tarjetas/{self.tarjeta.id}/bloquear/', {}, format='json'
        )
        bloqueo = Bloqueo.objects.get()
        self.assertEqual(self.api.post(f'/api/bloqueos/{bloqueo.id}/levantar/').status_code, 200)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'ACTIVA')

    def test_una_tarjeta_cancelada_no_se_puede_bloquear(self):
        self.tarjeta.estado = 'CANCELADA'
        self.tarjeta.save()
        self.assertEqual(self.bloquear(tipo='TARJETA', tarjeta=self.tarjeta.id).status_code, 409)

    def test_levantar_un_bloqueo_no_reactiva_una_tarjeta_que_se_cancelo(self):
        bloqueo_id = self.bloquear(tipo='TARJETA', tarjeta=self.tarjeta.id).json()['id']
        self.tarjeta.estado = 'CANCELADA'
        self.tarjeta.save()
        self.api.post(f'/api/bloqueos/{bloqueo_id}/levantar/')
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'CANCELADA')

    def test_datos_invalidos_responden_400(self):
        casos = {
            'tarjeta sin id': dict(tipo='TARJETA'),
            'comercio sin id': dict(tipo='COMERCIO'),
            'ambos': dict(tipo='TARJETA', tarjeta=self.tarjeta.id, comercio=self.comercio.id),
            'motivo vacío': dict(tipo='TARJETA', tarjeta=self.tarjeta.id, motivo=''),
            'tipo desconocido': dict(tipo='OTRO', tarjeta=self.tarjeta.id),
        }
        for nombre, datos in casos.items():
            with self.subTest(caso=nombre):
                self.assertEqual(self.bloquear(**datos).status_code, 400)
        self.assertFalse(Bloqueo.objects.exists())

    def test_un_id_inexistente_no_crea_el_bloqueo(self):
        respuesta = self.bloquear(tipo='TARJETA', tarjeta=999999)
        self.assertIn(respuesta.status_code, (400, 404))
        self.assertFalse(Bloqueo.objects.exists())

    def test_el_listado_trae_solo_los_vigentes_si_se_pide(self):
        vigente = self.bloquear(tipo='TARJETA', tarjeta=self.tarjeta.id).json()['id']
        levantado = self.bloquear(tipo='COMERCIO', comercio=self.comercio.id).json()['id']
        self.api.post(f'/api/bloqueos/{levantado}/levantar/')
        respuesta = self.api.get('/api/bloqueos/', {'vigentes': 'true'}).json()
        self.assertEqual([b['id'] for b in respuesta['results']], [vigente])


class RestriccionesDeBaseDeDatosTests(PlataformaTestCase):
    """La base de datos protege las reglas aunque el código falle."""

    def crear(self, **datos):
        with transaction.atomic():
            return Bloqueo.objects.create(origen='ANALISTA', motivo='Prueba', **datos)

    def test_un_bloqueo_no_puede_afectar_a_la_tarjeta_y_al_comercio_a_la_vez(self):
        with self.assertRaises(IntegrityError):
            self.crear(tipo='TARJETA', tarjeta=self.tarjeta, comercio=self.comercio)

    def test_un_bloqueo_no_puede_quedar_sin_objetivo(self):
        for tipo in ('TARJETA', 'COMERCIO'):
            with self.subTest(tipo=tipo), self.assertRaises(IntegrityError):
                self.crear(tipo=tipo)

    def test_el_tipo_debe_coincidir_con_el_objetivo(self):
        with self.assertRaises(IntegrityError):
            self.crear(tipo='COMERCIO', tarjeta=self.tarjeta)

    def test_solo_un_bloqueo_vigente_por_tarjeta_y_por_comercio(self):
        self.crear(tipo='TARJETA', tarjeta=self.tarjeta)
        with self.assertRaises(IntegrityError):
            self.crear(tipo='TARJETA', tarjeta=self.tarjeta)
        self.crear(tipo='COMERCIO', comercio=self.comercio)
        with self.assertRaises(IntegrityError):
            self.crear(tipo='COMERCIO', comercio=self.comercio)

    def test_el_cupo_disponible_no_puede_ser_negativo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tarjeta = type(self.tarjeta)
            Tarjeta.objects.filter(pk=self.tarjeta.pk).update(cupo_disponible=-1)


class AlertasTests(PlataformaTestCase):
    def setUp(self):
        super().setUp()
        self.analista = crear_usuario('ANALISTA')
        self.api = cliente(self.analista)

    def crear_alerta(self, tipo='RIESGO_ALTO_MODELO', **extra):
        compra = crear_compra(self.tarjeta, self.comercio)
        return Alerta.objects.create(
            tipo=tipo,
            autorizacion=compra,
            tarjeta=self.tarjeta,
            comercio=self.comercio,
            descripcion='Prueba',
            **extra,
        )

    def ids(self, **filtros):
        respuesta = self.api.get('/api/alertas/', filtros)
        self.assertEqual(respuesta.status_code, 200)
        return {a['id'] for a in respuesta.json()['results']}

    def test_la_bandeja_muestra_solo_las_pendientes_por_defecto(self):
        pendiente = self.crear_alerta()
        self.crear_alerta(estado='DESCARTADA')
        self.crear_alerta(estado='CONFIRMADA_FRAUDE')
        self.assertEqual(self.ids(), {pendiente.id})

    def test_filtro_por_tipo(self):
        modelo = self.crear_alerta('RIESGO_ALTO_MODELO')
        prueba = self.crear_alerta('PRUEBA_TARJETAS')
        self.assertEqual(self.ids(tipo='RIESGO_ALTO_MODELO'), {modelo.id})
        self.assertEqual(self.ids(tipo='PRUEBA_TARJETAS'), {prueba.id})

    def test_filtro_por_fecha(self):
        vieja = self.crear_alerta()
        reciente = self.crear_alerta()
        Alerta.objects.filter(pk=vieja.pk).update(
            fecha_creacion=datetime(2026, 1, 10, 15, 0, tzinfo=UTC)
        )
        self.assertEqual(self.ids(desde='2026-02-01'), {reciente.id})
        self.assertEqual(self.ids(hasta='2026-02-01'), {vieja.id})
        self.assertEqual(self.ids(desde='2026-01-01', hasta='2026-01-31'), {vieja.id})

    def test_el_detalle_trae_las_ultimas_autorizaciones_de_la_tarjeta(self):
        alerta = self.crear_alerta()
        for _ in range(12):
            crear_compra(self.tarjeta, self.comercio)
        detalle = self.api.get(f'/api/alertas/{alerta.id}/').json()
        compras = detalle['ultimas_autorizaciones']
        self.assertEqual(len(compras), 10)
        ids = [c['id'] for c in compras]
        self.assertEqual(ids, sorted(ids, reverse=True))  # la más reciente primero
        self.assertEqual(detalle['tarjeta_ultimos_4'], self.tarjeta.numero[-4:])

    def test_resolver_confirmando_fraude_no_bloquea_la_tarjeta(self):
        alerta = self.crear_alerta()
        url = f'/api/alertas/{alerta.id}/resolver/'
        respuesta = self.api.post(url, {'estado': 'CONFIRMADA_FRAUDE'}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, 'CONFIRMADA_FRAUDE')
        self.assertEqual(alerta.analista_id, self.analista.id)
        self.assertIsNotNone(alerta.fecha_resolucion)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.estado, 'ACTIVA')  # el bloqueo lo decide el analista

    def test_descartar_una_alerta(self):
        alerta = self.crear_alerta()
        url = f'/api/alertas/{alerta.id}/resolver/'
        self.assertEqual(
            self.api.post(url, {'estado': 'DESCARTADA'}, format='json').status_code, 200
        )
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, 'DESCARTADA')

    def test_una_alerta_resuelta_no_se_resuelve_otra_vez(self):
        alerta = self.crear_alerta()
        url = f'/api/alertas/{alerta.id}/resolver/'
        self.api.post(url, {'estado': 'DESCARTADA'}, format='json')
        self.assertEqual(
            self.api.post(url, {'estado': 'CONFIRMADA_FRAUDE'}, format='json').status_code, 409
        )
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, 'DESCARTADA')

    def test_resolver_con_un_estado_invalido_responde_400(self):
        alerta = self.crear_alerta()
        url = f'/api/alertas/{alerta.id}/resolver/'
        for estado in ('PENDIENTE', 'OTRO', ''):
            with self.subTest(estado=estado):
                self.assertEqual(
                    self.api.post(url, {'estado': estado}, format='json').status_code, 400
                )
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, 'PENDIENTE')

    def test_una_alerta_inexistente_responde_404(self):
        self.assertEqual(self.api.get('/api/alertas/999999/').status_code, 404)


class ReclamosTests(PlataformaTestCase):
    def setUp(self):
        super().setUp()
        self.compra = crear_compra(self.tarjeta, self.comercio, 75000)
        self.asociado_api = cliente(self.asociado.usuario)
        self.analista_api = cliente(crear_usuario('ANALISTA'))

    def radicar(self, descripcion='No reconozco esta compra'):
        return self.asociado_api.post(
            '/api/asociado/reclamos/',
            {'autorizacion': self.compra.id, 'descripcion': descripcion},
            format='json',
        )

    def test_el_asociado_radica_un_reclamo_sobre_su_compra(self):
        respuesta = self.radicar()
        self.assertEqual(respuesta.status_code, 201)
        reclamo = Reclamo.objects.get()
        self.assertEqual(reclamo.estado, 'RADICADO')
        self.assertEqual(reclamo.asociado_id, self.asociado.id)
        self.assertEqual(reclamo.autorizacion_id, self.compra.id)
        lista = self.asociado_api.get('/api/asociado/reclamos/').json()
        self.assertEqual(lista['count'], 1)

    def test_una_compra_se_reporta_una_sola_vez(self):
        self.radicar()
        self.assertIn(self.radicar().status_code, (400, 409))
        self.assertEqual(Reclamo.objects.count(), 1)

    def test_la_compra_aparece_como_reclamada_en_los_movimientos(self):
        url = f'/api/asociado/tarjetas/{self.tarjeta.id}/autorizaciones/'
        self.assertFalse(self.asociado_api.get(url).json()['results'][0]['reclamado'])
        self.radicar()
        self.assertTrue(self.asociado_api.get(url).json()['results'][0]['reclamado'])

    def test_descripcion_vacia_responde_400(self):
        self.assertEqual(self.radicar('').status_code, 400)
        self.assertFalse(Reclamo.objects.exists())

    def test_el_analista_ve_el_reclamo_y_lo_lleva_hasta_resuelto(self):
        self.radicar()
        reclamo = Reclamo.objects.get()
        url = f'/api/reclamos/{reclamo.id}/'
        lista = self.analista_api.get('/api/reclamos/').json()
        self.assertEqual([r['id'] for r in lista['results']], [reclamo.id])

        respuesta = self.analista_api.patch(url, {'estado': 'EN_REVISION'}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        reclamo.refresh_from_db()
        self.assertEqual((reclamo.estado, reclamo.fecha_resolucion), ('EN_REVISION', None))

        self.assertEqual(
            self.analista_api.patch(url, {'estado': 'RESUELTO'}, format='json').status_code, 200
        )
        reclamo.refresh_from_db()
        self.assertEqual(reclamo.estado, 'RESUELTO')
        self.assertIsNotNone(reclamo.fecha_resolucion)

    def test_un_reclamo_resuelto_no_se_reabre(self):
        self.radicar()
        reclamo = Reclamo.objects.get()
        url = f'/api/reclamos/{reclamo.id}/'
        self.analista_api.patch(url, {'estado': 'RESUELTO'}, format='json')
        for estado in ('RADICADO', 'EN_REVISION'):
            with self.subTest(estado=estado):
                respuesta = self.analista_api.patch(url, {'estado': estado}, format='json')
                self.assertIn(respuesta.status_code, (400, 409))
        reclamo.refresh_from_db()
        self.assertEqual(reclamo.estado, 'RESUELTO')

    def test_el_analista_filtra_los_reclamos_por_estado(self):
        self.radicar()
        reclamo = Reclamo.objects.get()

        def hay(estado):
            return self.analista_api.get('/api/reclamos/', {'estado': estado}).json()['count']

        self.assertEqual((hay('RADICADO'), hay('RESUELTO')), (1, 0))
        self.analista_api.patch(
            f'/api/reclamos/{reclamo.id}/', {'estado': 'RESUELTO'}, format='json'
        )
        self.assertEqual((hay('RADICADO'), hay('RESUELTO')), (0, 1))


class PerfilTests(PlataformaTestCase):
    def setUp(self):
        super().setUp()
        self.api = cliente(self.asociado.usuario)

    def test_el_asociado_cambia_celular_y_correo(self):
        respuesta = self.api.patch(
            '/api/asociado/perfil/',
            {'celular': '3109998877', 'email': 'nuevo@ejemplo.co'},
            format='json',
        )
        self.assertEqual(respuesta.status_code, 200)
        self.asociado.refresh_from_db()
        self.assertEqual(self.asociado.celular, '3109998877')
        self.assertEqual(self.asociado.email, 'nuevo@ejemplo.co')
        self.asociado.usuario.refresh_from_db()
        self.assertEqual(self.asociado.usuario.email, 'nuevo@ejemplo.co')

    def test_solo_se_pueden_cambiar_el_celular_y_el_correo(self):
        original = (self.asociado.nombres, self.asociado.numero_documento, self.asociado.ciudad)
        self.api.patch(
            '/api/asociado/perfil/',
            {
                'nombres': 'Otro',
                'numero_documento': '1',
                'ciudad': 'Bogotá',
                'estado': 'INACTIVO',
                'ingreso_anual': '1',
                'celular': '3109998877',
            },
            format='json',
        )
        self.asociado.refresh_from_db()
        self.assertEqual(
            (self.asociado.nombres, self.asociado.numero_documento, self.asociado.ciudad), original
        )
        self.assertEqual(self.asociado.estado, 'ACTIVO')
        self.assertEqual(self.asociado.celular, '3109998877')

    def test_celular_o_correo_invalidos_responden_400(self):
        for datos in ({'celular': 'abc'}, {'celular': '123'}, {'email': 'no-es-correo'}):
            with self.subTest(datos=datos):
                self.assertEqual(
                    self.api.patch('/api/asociado/perfil/', datos, format='json').status_code, 400
                )
        self.asociado.refresh_from_db()
        self.assertEqual(self.asociado.celular, '3001234567')
