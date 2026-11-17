import argparse
import json
import logging
import os
import signal
import sys
import time
import uuid
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import boto3
from kafka import KafkaConsumer, TopicPartition
from kafka.structs import OffsetAndMetadata

LOG = logging.getLogger('consumer')

LOTE_MENSAJES = 500
LOTE_SEGUNDOS = 60
INTENTOS_S3 = 3
ESPERA_INICIAL = 1.0
ESPERA_MAXIMA = 60.0


def clave_s3(prefijo: str, ahora: datetime, identificador: uuid.UUID | None = None) -> str:
    identificador = identificador or uuid.uuid4()
    return f'{prefijo.strip("/")}/{ahora:%Y/%m/%d/%H}/{ahora:%Y%m%dT%H%M%S}-{identificador}.json'


class Buffer:
    def __init__(self):
        self.lineas: list[bytes] = []
        self.siguientes: dict[tuple[str, int], int] = {}
        self.total = 0
        self.omitidos = 0

    def agregar(self, registro) -> None:
        self.total += 1
        self.siguientes[(registro.topic, registro.partition)] = registro.offset + 1
        valor = registro.value
        try:
            json.loads(valor)
        except (ValueError, TypeError):
            self.omitidos += 1
            LOG.warning(
                'Mensaje omitido (no es JSON) en %s[%d] offset %d',
                registro.topic,
                registro.partition,
                registro.offset,
            )
            return
        self.lineas.append(valor.rstrip(b'\r\n'))


def escribir_con_reintentos(s3, bucket: str, clave: str, cuerpo: bytes, dormir) -> None:
    espera = ESPERA_INICIAL
    for intento in range(1, INTENTOS_S3 + 1):
        try:
            s3.put_object(Bucket=bucket, Key=clave, Body=cuerpo, ContentType='application/x-ndjson')
            return
        except Exception as error:
            LOG.warning(
                'Falló la escritura en S3 (intento %d de %d): %s', intento, INTENTOS_S3, error
            )
            if intento == INTENTOS_S3:
                raise
            dormir(espera)
            espera *= 2


def confirmar(consumidor, siguientes: dict[tuple[str, int], int]) -> None:
    consumidor.commit(
        {
            TopicPartition(topic, particion): OffsetAndMetadata(offset, '', -1)
            for (topic, particion), offset in siguientes.items()
        }
    )


def volcar(consumidor, s3, args, buffer: Buffer, dormir, ahora: datetime | None = None) -> None:
    if buffer.lineas:
        ahora = ahora or datetime.now(UTC)
        clave = clave_s3(args.prefijo, ahora)
        cuerpo = b'\n'.join(buffer.lineas) + b'\n'
        escribir_con_reintentos(s3, args.bucket, clave, cuerpo, dormir)
        LOG.info('Escrito s3://%s/%s con %d eventos', args.bucket, clave, len(buffer.lineas))
    confirmar(consumidor, buffer.siguientes)
    LOG.info('Offsets confirmados: %s', dict(buffer.siguientes))


def crear_consumidor(args):
    return KafkaConsumer(
        args.topic,
        bootstrap_servers=args.bootstrap.split(','),
        group_id=args.grupo,
        enable_auto_commit=False,
        auto_offset_reset='earliest',
        max_poll_records=args.lote,
    )


def conectar(fabrica, dormir, detener):
    espera = ESPERA_INICIAL
    while not detener():
        try:
            return fabrica()
        except Exception as error:
            LOG.warning('Kafka no está disponible (%s); reintento en %.0f s', error, espera)
            dormir(espera)
            espera = min(espera * 2, ESPERA_MAXIMA)
    return None


def ejecutar(
    args, fabrica=None, s3=None, dormir=time.sleep, reloj=time.monotonic, detener=lambda: False
) -> None:
    fabrica = fabrica or (lambda: crear_consumidor(args))
    consumidor = conectar(fabrica, dormir, detener)
    if consumidor is None:
        return
    if s3 is None:
        s3 = boto3.client('s3')
    LOG.info(
        'Conectado a Kafka; grupo %s, topic %s, destino s3://%s/%s',
        args.grupo,
        args.topic,
        args.bucket,
        args.prefijo,
    )
    buffer = Buffer()
    ultimo = reloj()
    while not detener():
        for registros in consumidor.poll(timeout_ms=1000, max_records=args.lote).values():
            for registro in registros:
                buffer.agregar(registro)
        vencido = reloj() - ultimo >= args.segundos
        if buffer.total >= args.lote or (vencido and buffer.total):
            volcar(consumidor, s3, args, buffer, dormir)
            buffer = Buffer()
            ultimo = reloj()
        elif vencido:
            ultimo = reloj()
    if buffer.total:
        volcar(consumidor, s3, args, buffer, dormir)
    consumidor.close()


def configurar_logs(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    for manejador in (
        RotatingFileHandler(ruta, maxBytes=5_000_000, backupCount=3),
        logging.StreamHandler(),
    ):
        manejador.setFormatter(formato)
        LOG.addHandler(manejador)
    LOG.setLevel(logging.INFO)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Escribe en S3 los eventos del topic de Kafka')
    parser.add_argument('--bootstrap', default=os.environ.get('KAFKA_BOOTSTRAP'))
    parser.add_argument('--topic', default=os.environ.get('KAFKA_TOPIC', 'eventos'))
    parser.add_argument('--grupo', default=os.environ.get('KAFKA_GRUPO', 'eventos-s3-writer'))
    parser.add_argument('--bucket', default=os.environ.get('S3_BUCKET'))
    parser.add_argument('--prefijo', default=os.environ.get('S3_PREFIJO', 'raw/eventos'))
    parser.add_argument('--lote', type=int, default=LOTE_MENSAJES)
    parser.add_argument('--segundos', type=int, default=LOTE_SEGUNDOS)
    parser.add_argument('--log-file', type=Path, default=Path.home() / 'consumer_eventos.log')
    args = parser.parse_args(argv)
    if not args.bootstrap or not args.bucket:
        parser.error('Faltan --bootstrap y --bucket (o KAFKA_BOOTSTRAP y S3_BUCKET)')

    configurar_logs(args.log_file)
    detenido = False

    def pedir_parada(*_):
        nonlocal detenido
        detenido = True
        LOG.info('Parada solicitada; se vuelca el buffer y se termina')

    signal.signal(signal.SIGTERM, pedir_parada)
    signal.signal(signal.SIGINT, pedir_parada)
    try:
        ejecutar(args, detener=lambda: detenido)
    except Exception:
        LOG.exception('Error fatal; el offset no se confirmó y el lote se repetirá al reiniciar')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
