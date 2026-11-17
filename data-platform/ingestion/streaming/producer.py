import argparse
import json
import logging
import os
import re
import signal
import sys
import time
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from kafka import KafkaProducer

LOG = logging.getLogger('producer')

LOTE_MAXIMO = 500
SONDEO_SEGUNDOS = 1.0
ESPERA_INICIAL = 1.0
ESPERA_MAXIMA = 60.0


def listar_archivos(directorio: Path, nombre: str) -> list[Path]:
    if not directorio.is_dir():
        return []
    patron = re.compile(rf'^{re.escape(nombre)}\.\d{{4}}-\d{{2}}-\d{{2}}$')
    rotados = sorted(p for p in directorio.iterdir() if patron.match(p.name) and p.is_file())
    vivo = directorio / nombre
    return rotados + ([vivo] if vivo.is_file() else [])


class Estado:
    def __init__(self, ruta: Path):
        self.ruta = ruta

    def cargar(self) -> dict | None:
        try:
            return json.loads(self.ruta.read_text())
        except FileNotFoundError:
            return None
        except ValueError:
            LOG.warning('El archivo de estado está dañado; se empieza por el archivo más antiguo')
            return None

    def guardar(self, inode: int, offset: int) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix('.tmp')
        temporal.write_text(json.dumps({'inode': inode, 'offset': offset}))
        os.replace(temporal, self.ruta)


class Lector:
    def __init__(
        self, directorio: Path, nombre: str, estado: Estado, lote_maximo: int = LOTE_MAXIMO
    ):
        self.directorio = directorio
        self.nombre = nombre
        self.estado = estado
        self.lote_maximo = lote_maximo
        self.posicion = estado.cargar()

    def _ubicar(self, archivos: list[Path]) -> tuple[int, int]:
        if self.posicion:
            for indice, ruta in enumerate(archivos):
                try:
                    if ruta.stat().st_ino == self.posicion['inode']:
                        return indice, self.posicion['offset']
                except FileNotFoundError:
                    continue
            LOG.warning(
                'El archivo de la posición guardada ya no existe; se sigue con el más antiguo'
            )
        return 0, 0

    def leer_lote(self) -> tuple[list[bytes], dict | None]:
        archivos = listar_archivos(self.directorio, self.nombre)
        if not archivos:
            return [], None
        indice, offset = self._ubicar(archivos)
        lineas: list[bytes] = []
        posicion = None
        while indice < len(archivos):
            ruta = archivos[indice]
            try:
                archivo = ruta.open('rb')
            except FileNotFoundError:
                indice += 1
                offset = 0
                continue
            with archivo:
                info = os.fstat(archivo.fileno())
                if info.st_size < offset:
                    LOG.warning(
                        '%s es más corto que la posición guardada; se lee desde el inicio',
                        ruta.name,
                    )
                    offset = 0
                archivo.seek(offset)
                while len(lineas) < self.lote_maximo:
                    linea = archivo.readline()
                    if not linea.endswith(b'\n'):
                        break
                    lineas.append(linea)
                    offset = archivo.tell()
                posicion = {'inode': info.st_ino, 'offset': offset}
            if len(lineas) >= self.lote_maximo:
                break
            if ruta.name == self.nombre or indice + 1 >= len(archivos):
                break
            indice += 1
            offset = 0
        return lineas, posicion

    def confirmar(self, posicion: dict | None) -> None:
        if posicion and posicion != self.posicion:
            self.estado.guardar(posicion['inode'], posicion['offset'])
            self.posicion = posicion


def construir_mensaje(linea: bytes, ingestado: datetime) -> tuple[bytes | None, bytes] | None:
    try:
        evento = json.loads(linea)
    except ValueError:
        return None
    if not isinstance(evento, dict):
        return None
    evento['ingested_at'] = ingestado.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    id_usuario = evento.get('id_usuario')
    clave = None if id_usuario is None else str(id_usuario).encode('utf-8')
    valor = json.dumps(evento, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return clave, valor


def publicar_lote(productor, topic: str, lineas: list[bytes], ahora: datetime | None = None):
    ahora = ahora or datetime.now(UTC)
    futuros = []
    omitidas = 0
    for linea in lineas:
        mensaje = construir_mensaje(linea, ahora)
        if mensaje is None:
            omitidas += 1
            LOG.warning('Línea omitida, no es un evento JSON: %.200r', linea)
            continue
        futuros.append(productor.send(topic, key=mensaje[0], value=mensaje[1]))
    productor.flush()
    for futuro in futuros:
        futuro.get(timeout=30)
    return len(futuros), omitidas


def crear_productor(bootstrap: str):
    return KafkaProducer(
        bootstrap_servers=bootstrap.split(','),
        acks='all',
        retries=5,
        max_in_flight_requests_per_connection=1,
        linger_ms=50,
        request_timeout_ms=30000,
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


def ejecutar(args, fabrica=None, dormir=time.sleep, detener=lambda: False) -> None:
    fabrica = fabrica or (lambda: crear_productor(args.bootstrap))
    productor = conectar(fabrica, dormir, detener)
    if productor is None:
        return
    lector = Lector(args.directorio_log, args.nombre, Estado(args.estado))
    LOG.info(
        'Conectado a Kafka; leyendo %s/%s hacia el topic %s',
        args.directorio_log,
        args.nombre,
        args.topic,
    )
    espera = ESPERA_INICIAL
    while not detener():
        try:
            lineas, posicion = lector.leer_lote()
            if lineas:
                enviadas, omitidas = publicar_lote(productor, args.topic, lineas)
                lector.confirmar(posicion)
                LOG.info('Lote publicado: %d mensajes (%d omitidos)', enviadas, omitidas)
            else:
                lector.confirmar(posicion)
                dormir(SONDEO_SEGUNDOS)
            espera = ESPERA_INICIAL
        except Exception as error:
            LOG.error('Falló el envío (%s); se reintenta el mismo lote en %.0f s', error, espera)
            dormir(espera)
            espera = min(espera * 2, ESPERA_MAXIMA)
    try:
        productor.flush()
        productor.close()
    except Exception as error:
        LOG.warning('Error al cerrar el productor: %s', error)


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
    inicio = Path.home()
    parser = argparse.ArgumentParser(description='Publica en Kafka los eventos de eventos.log')
    parser.add_argument(
        '--directorio-log', type=Path, default=inicio / 'fraud-detection-platform' / 'logs'
    )
    parser.add_argument('--nombre', default='eventos.log')
    parser.add_argument('--bootstrap', default=os.environ.get('KAFKA_BOOTSTRAP'))
    parser.add_argument('--topic', default=os.environ.get('KAFKA_TOPIC', 'eventos'))
    parser.add_argument('--estado', type=Path, default=inicio / '.producer_eventos_estado.json')
    parser.add_argument('--log-file', type=Path, default=inicio / 'producer_eventos.log')
    args = parser.parse_args(argv)
    if not args.bootstrap:
        parser.error('Falta --bootstrap o la variable KAFKA_BOOTSTRAP (ej. 172.16.3.113:19092,...)')

    configurar_logs(args.log_file)
    detenido = False

    def pedir_parada(*_):
        nonlocal detenido
        detenido = True
        LOG.info('Parada solicitada; se termina el lote en curso')

    signal.signal(signal.SIGTERM, pedir_parada)
    signal.signal(signal.SIGINT, pedir_parada)
    ejecutar(args, detener=lambda: detenido)
    return 0


if __name__ == '__main__':
    sys.exit(main())
