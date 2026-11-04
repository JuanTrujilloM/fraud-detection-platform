"""Carga asociados, tarjetas y comercios desde CSV. Es idempotente y nunca sobrescribe lo existente,
para no reiniciar los cupos que ya se hayan consumido.

El directorio debe tener asociados.csv, comercios.csv y tarjetas.csv (ver data/muestra). Puede tener
además usuarios_internos.csv (analistas y administradores).
"""

import csv
import os
from collections.abc import Iterator
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tarjetas.cvv import hashear_cvv
from tarjetas.models import Tarjeta
from usuarios.models import Asociado, Comercio, Usuario

TAMANO_LOTE = 1000
DIRECTORIO_MUESTRA = Path(__file__).resolve().parents[3] / 'data' / 'muestra'


def _leer(ruta: Path) -> Iterator[dict[str, str]]:
    if not ruta.exists():
        raise CommandError(f'No existe el archivo {ruta}')
    with ruta.open(encoding='utf-8', newline='') as archivo:
        yield from csv.DictReader(archivo)


def _es_verdadero(valor: str) -> bool:
    return valor.strip().lower() in {'true', '1', 'si', 'sí', 'yes'}


class Command(BaseCommand):
    help = 'Carga asociados, tarjetas y comercios desde un directorio con CSV.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', type=Path, default=DIRECTORIO_MUESTRA)
        parser.add_argument(
            '--password',
            default=os.environ.get('CARGA_PASSWORD'),
            help='Contraseña de los usuarios creados. Sin ella (ni CARGA_PASSWORD) no entran.',
        )

    @transaction.atomic
    def handle(self, *args, dir: Path, password: str | None, **options):
        # Un solo hash para todos: con PBKDF2 hashear miles de usuarios tardaría minutos.
        hash_password = make_password(password)

        asociados = self._cargar_asociados(dir / 'asociados.csv', hash_password)
        comercios = self._cargar_comercios(dir / 'comercios.csv', hash_password)
        tarjetas = self._cargar_tarjetas(dir / 'tarjetas.csv')
        internos = self._cargar_internos(dir / 'usuarios_internos.csv', hash_password)

        self.stdout.write(
            self.style.SUCCESS(
                f'Filas leídas: {asociados} asociados, {comercios} comercios, '
                f'{tarjetas} tarjetas, {internos} usuarios internos.'
            )
        )

    def _crear_usuarios(self, usernames_emails: list[tuple[str, str]], rol, hash_password):
        Usuario.objects.bulk_create(
            [
                Usuario(username=username, email=email, rol=rol, password=hash_password)
                for username, email in usernames_emails
            ],
            batch_size=TAMANO_LOTE,
            ignore_conflicts=True,
        )
        return dict(
            Usuario.objects.filter(username__in=[u for u, _ in usernames_emails]).values_list(
                'username', 'id'
            )
        )

    def _cargar_asociados(self, ruta: Path, hash_password: str) -> int:
        filas = list(_leer(ruta))
        ids = self._crear_usuarios(
            [(f'asociado_{f["numero_documento"]}', f['email']) for f in filas],
            Usuario.Rol.ASOCIADO,
            hash_password,
        )
        Asociado.objects.bulk_create(
            [
                Asociado(
                    usuario_id=ids[f'asociado_{f["numero_documento"]}'],
                    tipo_documento=f['tipo_documento'],
                    numero_documento=f['numero_documento'],
                    nombres=f['nombres'],
                    apellidos=f['apellidos'],
                    fecha_nacimiento=f['fecha_nacimiento'],
                    ciudad=f['ciudad'],
                    celular=f['celular'],
                    email=f['email'],
                    ingreso_anual=f['ingreso_anual'],
                    puntaje_crediticio=f['puntaje_crediticio'],
                    fecha_afiliacion=f['fecha_afiliacion'],
                )
                for f in filas
            ],
            batch_size=TAMANO_LOTE,
            ignore_conflicts=True,
        )
        return len(filas)

    def _cargar_comercios(self, ruta: Path, hash_password: str) -> int:
        filas = list(_leer(ruta))
        categorias = set(Comercio.Categoria.values)
        for fila in filas:
            if fila['categoria'] not in categorias:
                raise CommandError(f'Categoría desconocida: {fila["categoria"]}')
        ids = self._crear_usuarios(
            [(f'comercio_{f["nit"]}', f.get('email', '')) for f in filas],
            Usuario.Rol.COMERCIO,
            hash_password,
        )
        Comercio.objects.bulk_create(
            [
                Comercio(
                    usuario_id=ids[f'comercio_{f["nit"]}'],
                    nombre=f['nombre'],
                    nit=f['nit'],
                    categoria=f['categoria'],
                    ciudad=f['ciudad'],
                    vende_en_linea=_es_verdadero(f['vende_en_linea']),
                )
                for f in filas
            ],
            batch_size=TAMANO_LOTE,
            ignore_conflicts=True,
        )
        return len(filas)

    def _cargar_tarjetas(self, ruta: Path) -> int:
        filas = list(_leer(ruta))
        asociados = dict(Asociado.objects.values_list('numero_documento', 'id'))
        tarjetas = []
        for f in filas:
            if f['numero_documento'] not in asociados:
                raise CommandError(
                    f'La tarjeta terminada en {f["numero"][-4:]} apunta a un asociado inexistente.'
                )
            tarjetas.append(
                Tarjeta(
                    asociado_id=asociados[f['numero_documento']],
                    numero=f['numero'],
                    ultimos_4=f['numero'][-4:],  # bulk_create no llama a save()
                    franquicia=f['franquicia'],
                    fecha_vencimiento=f['fecha_vencimiento'],
                    cvv_hash=hashear_cvv(f['numero'], f['cvv']),
                    tiene_chip=_es_verdadero(f['tiene_chip']),
                    cupo_total=f['cupo_total'],
                    cupo_disponible=f['cupo_total'],
                    fecha_emision=f['fecha_emision'],
                    estado=f.get('estado') or Tarjeta.Estado.ACTIVA,
                )
            )
        Tarjeta.objects.bulk_create(tarjetas, batch_size=TAMANO_LOTE, ignore_conflicts=True)
        return len(filas)

    def _cargar_internos(self, ruta: Path, hash_password: str) -> int:
        if not ruta.exists():
            return 0
        filas = list(_leer(ruta))
        for f in filas:
            # Con save() para que el rol ADMIN reciba los permisos del admin de Django.
            if not Usuario.objects.filter(username=f['username']).exists():
                Usuario(
                    username=f['username'], email=f['email'], rol=f['rol'], password=hash_password
                ).save()
        return len(filas)
