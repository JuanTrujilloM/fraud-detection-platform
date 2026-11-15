"""Simula la entrega semanal de contracargos de la red de pagos.

Escribe contracargos_AAAA-MM-DD.csv con los reclamos que el analista resolvió como fraude durante
la semana anterior a esa fecha (un lunes), con el mismo formato que los archivos del histórico.

El id_contracargo sale del id del reclamo, así que repetir la corrida da el mismo archivo.
"""

import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from portal.models import Reclamo

ENCABEZADO = [
    'id_contracargo',
    'id_autorizacion',
    'id_tarjeta',
    'ultimos_4',
    'monto',
    'fecha_compra',
    'fecha_contracargo',
    'motivo',
]
# Los contracargos del histórico usan ids bajos; los nuevos parten de aquí para no chocar con ellos.
DESPLAZAMIENTO_ID = 100_000


def _monto(valor: Decimal) -> str:
    return str(int(valor)) if valor == valor.to_integral_value() else f'{valor:.2f}'


def _fecha_local(momento: datetime) -> str:
    return timezone.localtime(momento).date().isoformat()


class Command(BaseCommand):
    help = 'Genera el archivo semanal de contracargos con los reclamos resueltos como fraude.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--semana-hasta',
            type=date.fromisoformat,
            help='Lunes de la entrega (AAAA-MM-DD). Por defecto, el lunes más reciente.',
        )
        parser.add_argument('--salida', default='/exports', help='Carpeta del archivo.')

    def handle(self, *args, semana_hasta, salida, **options):
        hoy = timezone.localdate()
        hasta = semana_hasta or hoy - timedelta(days=hoy.weekday())
        if hasta.weekday() != 0:
            raise CommandError(f'{hasta} no es lunes.')
        desde = hasta - timedelta(days=7)
        zona = timezone.get_current_timezone()
        reclamos = (
            Reclamo.objects.filter(
                estado=Reclamo.Estado.RESUELTO,
                resultado=Reclamo.Resultado.FRAUDE,
                fecha_resolucion__gte=datetime.combine(desde, time.min, tzinfo=zona),
                fecha_resolucion__lt=datetime.combine(hasta, time.min, tzinfo=zona),
            )
            .select_related('autorizacion__tarjeta')
            .order_by('fecha_resolucion', 'id')
        )

        ruta = Path(salida) / f'contracargos_{hasta.isoformat()}.csv'
        ruta.parent.mkdir(parents=True, exist_ok=True)
        filas = 0
        with ruta.open('w', encoding='utf-8', newline='') as archivo:
            escritor = csv.writer(archivo, lineterminator='\n')
            escritor.writerow(ENCABEZADO)
            for reclamo in reclamos.iterator():
                compra = reclamo.autorizacion
                escritor.writerow(
                    [
                        DESPLAZAMIENTO_ID + reclamo.id,
                        compra.id,
                        compra.tarjeta_id,
                        compra.tarjeta.ultimos_4,
                        _monto(compra.monto),
                        _fecha_local(compra.fecha_hora),
                        _fecha_local(reclamo.fecha_resolucion),
                        Reclamo.Resultado.FRAUDE,
                    ]
                )
                filas += 1
        self.stdout.write(
            self.style.SUCCESS(
                f'{ruta}: {filas} contracargos (del {desde} al {hasta}, sin incluirlo)'
            )
        )
