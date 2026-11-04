# Carga de datos

`python manage.py cargar_datos [--dir RUTA] [--password CLAVE]` lee estos CSV (UTF-8, con encabezado). Sin `--dir` usa `backend/data/muestra`.

Es idempotente y no sobrescribe lo existente: se puede volver a correr sin reiniciar cupos ni contraseñas. Si no recibe contraseña (por `--password` o `CARGA_PASSWORD`), los usuarios creados no pueden iniciar sesión.

| Archivo | Columnas |
| --- | --- |
| `asociados.csv` | `tipo_documento, numero_documento, nombres, apellidos, fecha_nacimiento, ciudad, celular, email, ingreso_anual, puntaje_crediticio, fecha_afiliacion` |
| `comercios.csv` | `nombre, nit, categoria, ciudad, vende_en_linea` y `email` (opcional) |
| `tarjetas.csv` | `numero_documento, numero, franquicia, fecha_vencimiento, cvv, tiene_chip, cupo_total, fecha_emision` y `estado` (opcional) |
| `usuarios_internos.csv` (opcional) | `username, email, rol` |

Los usuarios se crean como `asociado_<numero_documento>` y `comercio_<nit>`. Las fechas van en formato `AAAA-MM-DD`.

## Dataset histórico

La muestra de `backend/data/muestra` es sintética y la genera `scripts/generar_muestra.py`. Para cargar el dataset histórico hay que transformarlo a estas columnas, incluida la equivalencia de MCC a las categorías de `Comercio.Categoria`, y pasar la carpeta con `--dir`.
