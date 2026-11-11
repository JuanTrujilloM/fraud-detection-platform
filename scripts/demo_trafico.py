#!/usr/bin/env python3
"""Genera tráfico llamando a POST /api/autorizaciones/ como lo haría una terminal.

Lee las tarjetas y los comercios del histórico cargado en el OLTP (backend/data/historico). Solo
usa la biblioteca estándar.

    python scripts/demo_trafico.py --password <CARGA_PASSWORD> --compras 200
    python scripts/demo_trafico.py --password <CARGA_PASSWORD> --prueba-tarjetas
"""

import argparse
import csv
import json
import random
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / 'backend' / 'data' / 'historico'
# Con decenas de miles de comercios, la demo inicia sesión solo en una muestra de ellos.
COMERCIOS_DEMO = 20
# El ataque típico del enunciado: compras pequeñas de 40 tarjetas distintas en un comercio.
TARJETAS_PRUEBA = 40
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]


def post(url: str, cuerpo: dict, token: str | None = None) -> dict:
    encabezados = {'Content-Type': 'application/json', 'User-Agent': random.choice(USER_AGENTS)}
    if token:
        encabezados['Authorization'] = f'Bearer {token}'
    peticion = urllib.request.Request(  # noqa: S310 - la URL la da quien corre el script
        url, data=json.dumps(cuerpo).encode(), headers=encabezados, method='POST'
    )
    with urllib.request.urlopen(peticion, timeout=15) as respuesta:  # noqa: S310
        return json.load(respuesta)


def leer_csv(nombre: str) -> list[dict]:
    ruta = DATOS / nombre
    if not ruta.exists():
        raise SystemExit(f'No existe {ruta}: descomprime historico.zip en backend/data/historico.')
    with ruta.open(encoding='utf-8', newline='') as archivo:
        return list(csv.DictReader(archivo))


def vencimiento(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f'{fecha.month:02d}/{fecha.year % 100:02d}'


def compra_base(tarjeta: dict, monto: int, en_linea: bool) -> dict:
    compra = {
        'numero_tarjeta': tarjeta['numero'],
        'fecha_vencimiento': vencimiento(tarjeta['fecha_vencimiento']),
        'monto': str(monto),
        'canal': 'EN_LINEA' if en_linea else 'PRESENCIAL',
        'modo_lectura': 'DIGITADA' if en_linea else random.choice(['CHIP', 'BANDA']),
    }
    if en_linea:
        pegada = random.random() < 0.1
        compra |= {
            'cvv': tarjeta['cvv'],
            'huella_dispositivo': f'{random.getrandbits(32):08x}',
            'segundos_formulario': round(
                random.uniform(1, 4) if pegada else random.uniform(15, 90), 1
            ),
            'tarjeta_pegada': pegada,
        }
    return compra


def compra_aleatoria(tarjeta: dict, en_linea: bool) -> dict:
    """La mayoría son compras normales; algunas fallan a propósito para ver cada motivo."""
    compra = compra_base(tarjeta, random.randrange(10_000, 800_000, 1_000), en_linea)
    suerte = random.random()
    if suerte < 0.03:
        compra['numero_tarjeta'] = '4512349' + ''.join(random.choices('0123456789', k=9))
    elif suerte < 0.06:
        compra['fecha_vencimiento'] = '01/33'
    elif suerte < 0.09 and en_linea:
        compra['cvv'] = f'{(int(tarjeta["cvv"]) + 1) % 1000:03d}'
    elif suerte < 0.12:
        compra['monto'] = '90000000'
    return compra


def entrar(url: str, comercio: dict, password: str) -> str:
    datos = post(
        f'{url}/api/auth/login/', {'username': f'comercio_{comercio["nit"]}', 'password': password}
    )
    return datos['access']


def trafico_normal(url: str, password: str, cantidad: int, pausa: float) -> Counter:
    tarjetas = leer_csv('tarjetas.csv')
    todos = leer_csv('comercios.csv')
    comercios = random.sample(todos, k=min(COMERCIOS_DEMO, len(todos)))
    tokens = {c['nit']: entrar(url, c, password) for c in comercios}
    conteo: Counter = Counter()
    for _ in range(cantidad):
        comercio = random.choice(comercios)
        en_linea = comercio['vende_en_linea'].lower() == 'true' and random.random() < 0.6
        compra = compra_aleatoria(random.choice(tarjetas), en_linea)
        decision = post(f'{url}/api/autorizaciones/', compra, tokens[comercio['nit']])
        conteo[decision['motivo_rechazo'] or 'APROBADA'] += 1
        time.sleep(pausa)
    return conteo


def prueba_de_tarjetas(url: str, password: str, pausa: float) -> Counter:
    """Muchas tarjetas con compras pequeñas en un comercio: el patrón del plus de streaming."""
    tarjetas, comercios = leer_csv('tarjetas.csv'), leer_csv('comercios.csv')
    comercio = next(c for c in comercios if c['vende_en_linea'].lower() == 'true')
    token = entrar(url, comercio, password)
    conteo: Counter = Counter()
    for tarjeta in random.sample(tarjetas, k=min(TARJETAS_PRUEBA, len(tarjetas))):
        compra = compra_base(tarjeta, random.randrange(1_000, 5_000, 100), en_linea=True)
        compra |= {'tarjeta_pegada': True, 'segundos_formulario': round(random.uniform(1, 3), 1)}
        decision = post(f'{url}/api/autorizaciones/', compra, token)
        conteo[decision['motivo_rechazo'] or 'APROBADA'] += 1
        time.sleep(pausa)
    return conteo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:5173', help='Sin barra al final.')
    parser.add_argument('--password', required=True, help='La CARGA_PASSWORD de cargar_datos.')
    parser.add_argument('--compras', type=int, default=100)
    parser.add_argument('--pausa', type=float, default=0.05, help='Segundos entre compras.')
    parser.add_argument('--prueba-tarjetas', action='store_true')
    args = parser.parse_args()

    try:
        if args.prueba_tarjetas:
            conteo = prueba_de_tarjetas(args.url, args.password, args.pausa)
        else:
            conteo = trafico_normal(args.url, args.password, args.compras, args.pausa)
    except urllib.error.HTTPError as error:
        raise SystemExit(f'El servidor respondió {error.code} en {error.url}') from error
    except urllib.error.URLError as error:
        raise SystemExit(f'No se pudo conectar con {args.url}: {error.reason}') from error

    for motivo, cantidad in conteo.most_common():
        print(f'{cantidad:5d}  {motivo}')


if __name__ == '__main__':
    main()
