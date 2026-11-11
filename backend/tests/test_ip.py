"""IP del cliente detrás de proxies: ALB + Nginx en AWS son 2 saltos; en local, 1 (Vite)."""

from django.test import RequestFactory, SimpleTestCase, override_settings

from eventos.contexto import obtener_ip


class IpDelClienteTests(SimpleTestCase):
    def peticion(self, **cabeceras):
        return RequestFactory().get('/', **cabeceras)

    @override_settings(NUM_PROXIES=0)
    def test_sin_proxies_usa_la_ip_de_la_conexion(self):
        self.assertEqual(obtener_ip(self.peticion(REMOTE_ADDR='190.24.13.8')), '190.24.13.8')

    @override_settings(NUM_PROXIES=1)
    def test_un_proxy_en_local_toma_la_ultima_entrada(self):
        peticion = self.peticion(HTTP_X_FORWARDED_FOR='190.24.13.8', REMOTE_ADDR='172.18.0.4')
        self.assertEqual(obtener_ip(peticion), '190.24.13.8')

    @override_settings(NUM_PROXIES=2)
    def test_alb_mas_nginx_toman_la_ip_del_cliente(self):
        # El ALB agrega la IP del cliente y Nginx agrega la del ALB.
        peticion = self.peticion(
            HTTP_X_FORWARDED_FOR='190.24.13.8, 10.0.1.25', REMOTE_ADDR='172.18.0.4'
        )
        self.assertEqual(obtener_ip(peticion), '190.24.13.8')

    @override_settings(NUM_PROXIES=2)
    def test_una_cabecera_falsificada_por_el_cliente_no_engana_al_backend(self):
        peticion = self.peticion(
            HTTP_X_FORWARDED_FOR='1.1.1.1, 190.24.13.8, 10.0.1.25', REMOTE_ADDR='172.18.0.4'
        )
        self.assertEqual(obtener_ip(peticion), '190.24.13.8')

    @override_settings(NUM_PROXIES=1)
    def test_una_ip_invalida_en_la_cabecera_no_rompe_la_peticion(self):
        peticion = self.peticion(HTTP_X_FORWARDED_FOR='no-es-una-ip', REMOTE_ADDR='172.18.0.4')
        resultado = obtener_ip(peticion)
        self.assertTrue(resultado is None or resultado == '172.18.0.4')
