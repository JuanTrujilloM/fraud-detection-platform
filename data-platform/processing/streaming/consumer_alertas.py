"""Lee las alertas que publica Flink en Kafka y las envía al backend.

Cada mensaje del topic alertas-streaming se envía a POST /api/alertas/streaming/, que crea la
alerta y bloquea el comercio. El offset se confirma solo después de procesar el mensaje: si el
backend no responde o falla (5xx), se reintenta el mismo mensaje sin perderlo. Las alertas que el
backend rechaza (400 o 404) se registran en el log y se descartan.
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests

LOG = logging.getLogger('consumer_alertas')

ESPERA_INICIAL = 1.0
ESPERA_MAXIMA = 60.0
TIEMPO_LIMITE_HTTP = 10


class CredencialesInvalidas(Exception):
    """El backend rechazó el usuario de servicio: reintentar no lo arregla."""


class Parada:
    """Marca que se activa con SIGTERM o SIGINT para terminar después del mensaje en curso."""

    def __init__(self):
        self.solicitada = False

    def pedir(self, *_):
        self.solicitada = True
        LOG.info('Parada solicitada; se termina después del mensaje en curso')

    def detener(self) -> bool:
        return self.solicitada


class ClienteApi:
    def __init__(self, url: str, usuario: str, clave: str):
        self.url = url.rstrip('/')
        self.usuario = usuario
        self.clave = clave
        self.token = None
        self.sesion = requests.Session()

    def iniciar_sesion(self) -> None:
        respuesta = self.sesion.post(
            f'{self.url}/api/auth/login/',
            json={'username': self.usuario, 'password': self.clave},
            timeout=TIEMPO_LIMITE_HTTP,
        )
        if respuesta.status_code in (400, 401):
            raise CredencialesInvalidas(
                f'El backend rechazó el usuario {self.usuario} ({respuesta.status_code})'
            )
        # Un 5xx sale como excepción de requests y se reintenta como un error de red.
        respuesta.raise_for_status()
        self.token = respuesta.json()['access']
        LOG.info('Sesión iniciada en %s como %s', self.url, self.usuario)

    def _publicar(self, alerta: dict) -> requests.Response:
        return self.sesion.post(
            f'{self.url}/api/alertas/streaming/',
            json=alerta,
            headers={'Authorization': f'Bearer {self.token}'},
            timeout=TIEMPO_LIMITE_HTTP,
        )

    def enviar(self, alerta: dict) -> requests.Response:
        if self.token is None:
            self.iniciar_sesion()
        respuesta = self._publicar(alerta)
        if respuesta.status_code == 401:
            # El token venció: se inicia sesión otra vez y se reenvía la misma alerta.
            LOG.info('El token venció; se inicia sesión de nuevo')
            self.iniciar_sesion()
            respuesta = self._publicar(alerta)
        return respuesta


def procesar(cliente: ClienteApi, alerta: dict, dormir, detener) -> bool:
    """Envía la alerta hasta que el backend la procese o la descarte.

    Devuelve False solo si se pidió parar antes de terminar; en ese caso el offset no se confirma
    y el mensaje se vuelve a leer al reiniciar.
    """
    espera = ESPERA_INICIAL
    while not detener():
        try:
            respuesta = cliente.enviar(alerta)
        except requests.RequestException as error:
            LOG.warning('No se pudo enviar la alerta (%s); reintento en %.0f s', error, espera)
        else:
            codigo = respuesta.status_code
            if codigo in (200, 201):
                LOG.info('Alerta procesada (%d): %s -> %s', codigo, alerta, respuesta.text)
                return True
            if codigo in (400, 404):
                LOG.warning('Alerta descartada (%d): %s -> %s', codigo, alerta, respuesta.text)
                return True
            if codigo < 500:
                # Por ejemplo 403: el usuario no tiene el rol SERVICIO. Reintentar no lo arregla.
                raise RuntimeError(f'El backend respondió {codigo}: {respuesta.text}')
            LOG.warning('El backend respondió %d; reintento en %.0f s', codigo, espera)
        dormir(espera)
        espera = min(espera * 2, ESPERA_MAXIMA)
    return False


def leer_alerta(registro) -> dict | None:
    try:
        alerta = json.loads(registro.value)
    except (ValueError, TypeError):
        return None
    if not isinstance(alerta, dict):
        return None
    return alerta


def confirmar(consumidor, registro) -> None:
    from kafka import TopicPartition
    from kafka.structs import OffsetAndMetadata

    particion = TopicPartition(registro.topic, registro.partition)
    consumidor.commit({particion: OffsetAndMetadata(registro.offset + 1, '', -1)})


def crear_consumidor(args):
    from kafka import KafkaConsumer

    return KafkaConsumer(
        args.topic,
        bootstrap_servers=args.bootstrap.split(','),
        group_id=args.grupo,
        enable_auto_commit=False,
        auto_offset_reset='earliest',
    )


def conectar(args, dormir, detener):
    espera = ESPERA_INICIAL
    while not detener():
        try:
            return crear_consumidor(args)
        except Exception as error:
            LOG.warning('Kafka no está disponible (%s); reintento en %.0f s', error, espera)
            dormir(espera)
            espera = min(espera * 2, ESPERA_MAXIMA)
    return None


def ejecutar(args, cliente: ClienteApi, dormir=time.sleep, detener=None) -> None:
    if detener is None:
        detener = Parada().detener
    consumidor = conectar(args, dormir, detener)
    if consumidor is None:
        return
    LOG.info(
        'Conectado a Kafka; grupo %s, topic %s, destino %s', args.grupo, args.topic, cliente.url
    )
    try:
        while not detener():
            lotes = consumidor.poll(timeout_ms=1000)
            for particion in lotes:
                registros = lotes[particion]
                for i in range(len(registros)):
                    registro = registros[i]
                    alerta = leer_alerta(registro)
                    if alerta is None:
                        LOG.warning(
                            'Mensaje descartado (no es un objeto JSON) en %s[%d] offset %d',
                            registro.topic,
                            registro.partition,
                            registro.offset,
                        )
                    elif not procesar(cliente, alerta, dormir, detener):
                        return
                    confirmar(consumidor, registro)
    finally:
        consumidor.close()


def configurar_logs(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    manejadores = [RotatingFileHandler(ruta, maxBytes=5_000_000, backupCount=3)]
    manejadores.append(logging.StreamHandler())
    for i in range(len(manejadores)):
        manejadores[i].setFormatter(formato)
        LOG.addHandler(manejadores[i])
    LOG.setLevel(logging.INFO)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Envía al backend las alertas de Flink')
    parser.add_argument('--bootstrap', default=os.environ.get('KAFKA_BOOTSTRAP'))
    parser.add_argument('--topic', default=os.environ.get('KAFKA_TOPIC', 'alertas-streaming'))
    parser.add_argument('--grupo', default=os.environ.get('KAFKA_GRUPO', 'consumidor-alertas'))
    parser.add_argument('--api-url', default=os.environ.get('API_URL'))
    parser.add_argument('--log-file', type=Path, default=Path.home() / 'consumer_alertas.log')
    args = parser.parse_args(argv)
    # La contraseña solo se toma del entorno, para que no quede visible en la lista de procesos.
    usuario = os.environ.get('API_USUARIO')
    clave = os.environ.get('API_PASSWORD')
    if not args.bootstrap or not args.api_url or not usuario or not clave:
        parser.error('Faltan KAFKA_BOOTSTRAP, API_URL, API_USUARIO o API_PASSWORD')

    configurar_logs(args.log_file)
    parada = Parada()
    signal.signal(signal.SIGTERM, parada.pedir)
    signal.signal(signal.SIGINT, parada.pedir)
    try:
        ejecutar(args, ClienteApi(args.api_url, usuario, clave), detener=parada.detener)
    except Exception:
        LOG.exception('Error fatal; el offset no se confirmó y la alerta se repetirá al reiniciar')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
