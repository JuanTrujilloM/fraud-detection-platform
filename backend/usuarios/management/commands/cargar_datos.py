"""Carga asociados, tarjetas y comercios desde CSV. Es idempotente y nunca sobrescribe lo existente,
para no reiniciar los cupos que ya se hayan consumido.

El directorio debe tener asociados.csv, comercios.csv y tarjetas.csv (ver docs/carga-de-datos.md).
Puede tener
además usuarios_internos.csv (analistas y administradores), autorizaciones.csv y reclamos.csv
(el histórico, con las columnas de cada tabla) y meta.json.

Si los CSV traen una columna `id`, se conserva: así el histórico del data lake y el OLTP comparten
llaves. meta.json puede indicar `ultimo_id_autorizacion` para que las autorizaciones nuevas no
choquen con las del histórico.
"""

import csv
import json
import os
from collections.abc import Iterator
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from autorizaciones.models import Autorizacion
from portal.models import Reclamo
from tarjetas.cvv import hashear_cvv
from tarjetas.models import Tarjeta
from usuarios.models import Asociado, Comercio, Usuario

TAMANO_LOTE = 1000
# PostgreSQL admite como máximo 65.535 parámetros por consulta.
TAMANO_CONSULTA = 10_000


def _leer(ruta: Path) -> Iterator[dict[str, str]]:
    if not ruta.exists():
        raise CommandError(f'No existe el archivo {ruta}')
    with ruta.open(encoding='utf-8', newline='') as archivo:
        yield from csv.DictReader(archivo)


def _es_verdadero(valor: str) -> bool:
    return valor.strip().lower() in {'true', '1', 'si', 'sí', 'yes'}


def _verificar_ids(modelo, campo: str, filas: list[dict[str, str]]) -> None:
    """Con ids explícitos, ignore_conflicts también ignoraría un id ocupado por otro registro, por
    ejemplo de una carga anterior. Eso desalinearía el OLTP con el data lake, así que se aborta."""
    esperados = {int(f['id']): f[campo] for f in filas if f.get('id')}
    ids = list(esperados)
    for i in range(0, len(ids), TAMANO_CONSULTA):
        lote = ids[i : i + TAMANO_CONSULTA]
        for id_, valor in modelo.objects.filter(id__in=lote).values_list('id', campo):
            if valor != esperados[id_]:
                raise CommandError(
                    f'El id {id_} de {modelo._meta.db_table} ya existe con otros datos. '
                    'Carga el histórico en una base de datos vacía.'
                )


def _id(fila: dict[str, str]) -> dict[str, int]:
    """Conserva el id del archivo si viene; si no, lo asigna la base de datos."""
    return {'id': int(fila['id'])} if fila.get('id') else {}


class Command(BaseCommand):
    help = 'Carga asociados, tarjetas y comercios desde un directorio con CSV.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir', type=Path, required=True, help='Carpeta con los CSV, p. ej. data/historico.'
        )
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
        # Las autorizaciones no tocan los cupos: el histórico ya está reflejado en cada tarjeta.
        autorizaciones = self._copiar(Autorizacion, dir / 'autorizaciones.csv')
        reclamos = self._copiar(Reclamo, dir / 'reclamos.csv')
        internos = self._cargar_internos(dir / 'usuarios_internos.csv', hash_password)
        self._ajustar_secuencias(dir / 'meta.json')

        self.stdout.write(
            self.style.SUCCESS(
                f'Filas leídas: {asociados} asociados, {comercios} comercios, '
                f'{tarjetas} tarjetas, {autorizaciones} autorizaciones, {reclamos} reclamos, '
                f'{internos} usuarios internos.'
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
        usernames = [u for u, _ in usernames_emails]
        ids = {}
        for i in range(0, len(usernames), TAMANO_CONSULTA):
            lote = usernames[i : i + TAMANO_CONSULTA]
            ids.update(Usuario.objects.filter(username__in=lote).values_list('username', 'id'))
        return ids

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
                    **_id(f),
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
        _verificar_ids(Asociado, 'numero_documento', filas)
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
                    **_id(f),
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
        _verificar_ids(Comercio, 'nit', filas)
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
                    **_id(f),
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
        _verificar_ids(Tarjeta, 'numero', filas)
        return len(filas)

    def _copiar(self, modelo, ruta: Path) -> int:
        """Carga una tabla del histórico con COPY: son millones de filas y bulk_create tardaría
        mucho. Pasa por una tabla temporal para que repetir la carga no duplique nada."""
        if not ruta.exists():
            return 0
        tabla = modelo._meta.db_table
        with ruta.open(encoding='utf-8', newline='') as archivo:
            encabezado = next(csv.reader(archivo))
        columnas_tabla = {campo.column for campo in modelo._meta.concrete_fields}
        desconocidas = set(encabezado) - columnas_tabla
        if desconocidas or 'id' not in encabezado:
            raise CommandError(
                f'{ruta.name} debe tener las columnas de la tabla {tabla}, con id. '
                f'Sobran: {sorted(desconocidas)}'
            )
        columnas = ', '.join(f'"{c}"' for c in encabezado)
        # Las fechas automáticas que no trae el archivo, como fecha_actualizacion, toman la hora
        # de la carga, igual que si Django guardara el registro.
        automaticas = [
            campo.column
            for campo in modelo._meta.concrete_fields
            if getattr(campo, 'auto_now', False) or getattr(campo, 'auto_now_add', False)
            if campo.column not in encabezado
        ]
        destino = ', '.join([columnas, *(f'"{c}"' for c in automaticas)])
        origen = ', '.join([columnas, *('now()' for _ in automaticas)])
        temporal = f'carga_{tabla}'
        with connection.cursor() as cursor:
            # Solo las columnas del archivo: las demás se completan al insertar.
            cursor.execute(
                f'CREATE TEMP TABLE {temporal} ON COMMIT DROP AS '  # noqa: S608
                f'SELECT {columnas} FROM {tabla} WITH NO DATA'
            )
            # En formato CSV, una celda vacía sin comillas es NULL.
            with (
                ruta.open('rb') as archivo,
                cursor.copy(
                    f'COPY {temporal} ({columnas}) FROM STDIN WITH (FORMAT csv, HEADER true)'
                ) as copia,
            ):
                while bloque := archivo.read(1 << 20):
                    copia.write(bloque)
            cursor.execute(
                f'INSERT INTO {tabla} ({destino}) SELECT {origen} '  # noqa: S608
                f'FROM {temporal} ON CONFLICT DO NOTHING'
            )
            cursor.execute(f'SELECT count(*) FROM {temporal}')  # noqa: S608
            return cursor.fetchone()[0]

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

    def _ajustar_secuencias(self, ruta_meta: Path) -> None:
        """Con ids explícitos, las secuencias quedan atrás y el siguiente INSERT chocaría."""
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(
                no_style(), [Asociado, Comercio, Tarjeta, Reclamo]
            ):
                cursor.execute(sql)
            if not ruta_meta.exists():
                return
            ultimo = int(
                json.loads(ruta_meta.read_text(encoding='utf-8'))['ultimo_id_autorizacion']
            )
            tabla = Autorizacion._meta.db_table
            cursor.execute(
                f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), "  # noqa: S608
                f'GREATEST(%s, (SELECT COALESCE(MAX(id), 1) FROM {tabla})))',
                [ultimo],
            )
