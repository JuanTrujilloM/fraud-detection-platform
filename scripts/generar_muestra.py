#!/usr/bin/env python3
"""Genera los CSV sintéticos de backend/data/muestra, siempre iguales (semilla fija)."""

import csv
import random
from datetime import date
from pathlib import Path

DESTINO = Path(__file__).resolve().parents[1] / 'backend' / 'data' / 'muestra'
CANTIDAD_ASOCIADOS = 30

NOMBRES = 'Ana Luis Marta Carlos Sofía Andrés Laura Julián Paula Diego Camila Mateo'.split()
APELLIDOS = 'Restrepo Gómez Vélez Montoya Zapata Arango Cardona Ríos Ochoa Mejía'.split()
CIUDADES = ['Medellín', 'Envigado', 'Itagüí', 'Bello', 'Rionegro', 'Sabaneta']
COMERCIOS = [
    ('Éxito Laureles', 'SUPERMERCADO', 'Medellín', False),
    ('Ferretería El Roble', 'HOGAR', 'Envigado', False),
    ('Terpel Las Palmas', 'COMBUSTIBLE', 'Medellín', False),
    ('Restaurante La Fonda', 'RESTAURANTE', 'Rionegro', False),
    ('Farmacia San Jorge', 'FARMACIA', 'Itagüí', True),
    ('TecnoAndina', 'ELECTRONICA', 'Medellín', True),
    ('Moda Paisa', 'ROPA', 'Sabaneta', True),
    ('Viajes Antioquia', 'VIAJES', 'Medellín', True),
    ('Cine Colombia Santafé', 'ENTRETENIMIENTO', 'Medellín', True),
    ('EPM Pagos', 'SERVICIOS_PUBLICOS', 'Medellín', True),
    ('Metro Recargas', 'TRANSPORTE', 'Bello', True),
    ('Variedades La 70', 'OTROS', 'Medellín', False),
]


def _digito_luhn(parcial: str) -> str:
    suma = 0
    for i, digito in enumerate(reversed(parcial)):
        d = int(digito)
        if i % 2 == 0:
            d = d * 2 - 9 if d > 4 else d * 2
        suma += d
    return str((10 - suma % 10) % 10)


def _numero_tarjeta(azar: random.Random, bin_: str) -> str:
    cuerpo = bin_ + ''.join(azar.choices('0123456789', k=9))
    return cuerpo + _digito_luhn(cuerpo)


def _escribir(nombre: str, filas: list[dict]) -> None:
    with (DESTINO / nombre).open('w', encoding='utf-8', newline='') as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=filas[0].keys())
        escritor.writeheader()
        escritor.writerows(filas)


def main() -> None:
    azar = random.Random(2026)  # noqa: S311 - datos sintéticos, no criptografía
    DESTINO.mkdir(parents=True, exist_ok=True)

    asociados, tarjetas = [], []
    for i in range(1, CANTIDAD_ASOCIADOS + 1):
        documento = f'10{i:08d}'
        nombre, apellido = azar.choice(NOMBRES), azar.choice(APELLIDOS)
        asociados.append(
            {
                'tipo_documento': 'CC',
                'numero_documento': documento,
                'nombres': nombre,
                'apellidos': f'{apellido} {azar.choice(APELLIDOS)}',
                'fecha_nacimiento': date(azar.randint(1960, 2003), azar.randint(1, 12), 15),
                'ciudad': azar.choice(CIUDADES),
                'celular': f'3{azar.randint(100000000, 199999999)}',
                'email': f'asociado{i}@coopandina.example',
                'ingreso_anual': azar.randrange(18_000_000, 180_000_000, 500_000),
                'puntaje_crediticio': azar.randint(420, 820),
                'fecha_afiliacion': date(azar.randint(2012, 2024), azar.randint(1, 12), 1),
            }
        )
        for _ in range(azar.choice([1, 1, 2])):
            franquicia, bin_ = azar.choice([('VISA', '451234'), ('MASTERCARD', '545454')])
            tarjetas.append(
                {
                    'numero_documento': documento,
                    'numero': _numero_tarjeta(azar, bin_),
                    'franquicia': franquicia,
                    'fecha_vencimiento': date(azar.randint(2028, 2031), azar.randint(1, 12), 28),
                    'cvv': f'{azar.randint(0, 999):03d}',
                    'tiene_chip': azar.random() > 0.15,
                    'cupo_total': azar.randrange(2_000_000, 20_000_000, 500_000),
                    'fecha_emision': date(azar.randint(2022, 2025), azar.randint(1, 12), 1),
                    'estado': 'ACTIVA',
                }
            )

    # Casos para que el tráfico de demo muestre cada motivo de rechazo.
    tarjetas[-1]['estado'] = 'CANCELADA'
    tarjetas[-2]['fecha_vencimiento'] = date(2024, 6, 30)

    comercios = [
        {
            'nombre': nombre,
            'nit': f'9001000{i:02d}',
            'categoria': categoria,
            'ciudad': ciudad,
            'vende_en_linea': en_linea,
            'email': f'comercio{i}@coopandina.example',
        }
        for i, (nombre, categoria, ciudad, en_linea) in enumerate(COMERCIOS, start=1)
    ]
    internos = [
        {'username': 'analista_demo', 'email': 'analista@coopandina.example', 'rol': 'ANALISTA'},
        {'username': 'admin_demo', 'email': 'admin@coopandina.example', 'rol': 'ADMIN'},
    ]

    _escribir('asociados.csv', asociados)
    _escribir('tarjetas.csv', tarjetas)
    _escribir('comercios.csv', comercios)
    _escribir('usuarios_internos.csv', internos)
    print(f'{len(asociados)} asociados, {len(tarjetas)} tarjetas, {len(comercios)} comercios')


if __name__ == '__main__':
    main()
