# Carga de datos

`python manage.py cargar_datos --dir RUTA [--password CLAVE]` lee estos CSV (UTF-8, con encabezado). El histórico del proyecto se comparte como `historico.zip`, que se descomprime en `backend/data/historico`.

Es idempotente y no sobrescribe lo existente: se puede volver a correr sin reiniciar cupos ni contraseñas. Si no recibe contraseña (por `--password` o `CARGA_PASSWORD`), los usuarios creados no pueden iniciar sesión.

| Archivo | Columnas |
| --- | --- |
| `asociados.csv` | `id, tipo_documento, numero_documento, nombres, apellidos, fecha_nacimiento, ciudad, celular, email, ingreso_anual, puntaje_crediticio, fecha_afiliacion` |
| `comercios.csv` | `id, nombre, nit, categoria, ciudad, vende_en_linea` y `email` (opcional) |
| `tarjetas.csv` | `id, numero_documento, numero, franquicia, fecha_vencimiento, cvv, tiene_chip, cupo_total, fecha_emision` y `estado` (opcional) |
| `usuarios_internos.csv` (opcional) | `username, email, rol` |
| `autorizaciones.csv` (opcional) | Las columnas de la tabla `autorizacion`, con `id`. Se carga con `COPY` y una celda vacía es nulo |
| `reclamos.csv` (opcional) | Las columnas de la tabla `reclamo`, con `id`. Igual que las autorizaciones |

La columna `id` es opcional en todos los archivos. Los usuarios se crean como `asociado_<numero_documento>` y `comercio_<nit>`. Las fechas van en formato `AAAA-MM-DD`.

## Ids explícitos

Si los CSV traen una columna `id`, se conserva, y las secuencias de PostgreSQL se ajustan al final. Si además hay un `meta.json` con `ultimo_id_autorizacion`, las autorizaciones nuevas empiezan después de ese id.

Con ids explícitos la carga va en una base de datos vacía: si un id ya está ocupado por otro registro, el comando se detiene sin guardar nada.
