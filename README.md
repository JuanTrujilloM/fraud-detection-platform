# Plataforma OLTP de CoopAndina

Autoriza las compras con tarjeta de crédito de la cooperativa y registra cada operación de negocio en un log de eventos que alimenta la ingesta por streaming. Es la fuente de datos de la plataforma de detección de fraude del proyecto SI3008.

| Capa | Tecnología |
| --- | --- |
| Backend | Django + Django REST Framework, servido con Gunicorn |
| Autenticación | JWT con `djangorestframework-simplejwt`, un rol por usuario |
| Base de datos | PostgreSQL |
| Frontend | Vue 3 + Vite + TypeScript, con rutas por rol |

## Cómo levantarla

Necesitas Docker.

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

Los datos son el histórico de CoopAndina, construido a partir de un dataset de Kaggle. No está en el repositorio: pide al equipo el archivo `historico.zip` y descomprímelo en `backend/data/historico/`. Después, en otra terminal, cárgalo (usa la `CARGA_PASSWORD` de tu `.env` como contraseña de todos los usuarios):

```bash
docker compose exec backend python manage.py cargar_datos --dir data/historico
```

Entra a <http://localhost:5173>:

| Rol | Usuario | Módulo |
| --- | --- | --- |
| Comercio con tienda en línea | `comercio_800026831` (Tecnología 26831) | Terminal de pago |
| Comercio solo presencial | `comercio_800000037` (Supermercado 37) | Terminal de pago |
| Asociado | `asociado_7000000825` | Portal |
| Analista | `analista_demo` | Consola de fraude |
| Administrador | `admin_demo` | [Admin de Django](http://localhost:5173/admin/) |

Cualquier comercio o asociado del histórico sirve: los usuarios son `comercio_<nit>` y `asociado_<documento>`. Las tarjetas, con su CVV en claro porque son sintéticas, quedan en `backend/data/historico/tarjetas.csv`. Muchas ya están vencidas, como en el dataset original.

Para generar tráfico:

```bash
python3 scripts/demo_trafico.py --password <CARGA_PASSWORD> --compras 200
```

El script también tiene `--prueba-tarjetas`, que simula el ataque que debe detectar el procesamiento en streaming.

El modelo de ML todavía devuelve un valor fijo bajo, así que no aparecerán alertas. Para verlas, sube `MODELO_PROBABILIDAD_FIJA` en `.env` (por ejemplo a `0.7` para aprobar con alerta o a `0.9` para rechazar) y recrea el contenedor:

```bash
docker compose up -d --force-recreate backend
```

## Despliegue en AWS

En la EC2, con `docker-compose.prod.yml`: Nginx sirve el build de Vue en el puerto 80 y reenvía `/api/`, `/admin/` y `/static/` a Gunicorn. El health check del ALB es `/healthz`.

En el `.env` de la EC2, además de los secretos propios y los datos de RDS:

| Variable | Valor |
| --- | --- |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | El DNS del ALB |
| `NUM_PROXIES` | `2`, por el ALB y Nginx |
| `POSTGRES_HOST` | El endpoint de RDS |

En orden:

1. Descomprime `historico.zip` en `backend/data/historico/`.
2. Levanta la aplicación, que aplica las migraciones al arrancar:

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

3. Carga el histórico en RDS, con la base vacía:

   ```bash
   docker compose -f docker-compose.prod.yml exec backend python manage.py cargar_datos --dir data/historico
   ```

4. Solo después, corre la primera ingesta por batch. La de autorizaciones usa `fecha_hora` como marca de agua: si corre antes de cargar el histórico, nunca tomará esas compras.

Los contracargos del histórico (`backend/data/historico/contracargos/`) no van a RDS: se suben directo a la zona raw del data lake.

## Procesamiento en streaming

Flink lee el topic `eventos` y detecta pruebas de tarjetas: un comercio con compras pequeñas de varias tarjetas distintas en ventanas de 5 minutos que avanzan cada minuto. Cada detección va al topic `alertas-streaming`, y `consumer_alertas.py` la envía a `POST /api/alertas/streaming/`, que crea la alerta, bloquea el comercio y lo registra en el log de eventos. Los archivos están en `data-platform/processing/streaming/`.

### Flink en `vm-flink`

En `data-platform/processing/streaming/`, descarga el conector de Kafka en `lib/`:

```bash
mkdir -p lib && curl -L -o lib/flink-sql-connector-kafka-3.4.0-1.20.jar https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.4.0-1.20/flink-sql-connector-kafka-3.4.0-1.20.jar
```

Levanta Flink:

```bash
docker compose up -d
```

Copia la consulta al jobmanager y ejecútala:

```bash
docker compose cp deteccion.sql jobmanager:/opt/flink/deteccion.sql
```

```bash
docker compose exec jobmanager /opt/flink/bin/sql-client.sh -f /opt/flink/deteccion.sql
```

El job queda corriendo en la interfaz de Flink, en el puerto 8081.

### Usuario de servicio

El consumer entra al backend con un usuario de rol `SERVICIO`, que solo puede enviar alertas. Créalo en el admin de Django (`/admin/`): Agregar usuario, con rol **Servicio**.

### `consumer-alertas.service`

En la máquina donde corre el consumer, instala `requests` en el entorno virtual del streaming:

```bash
/home/ubuntu/streaming-venv/bin/pip install requests
```

Guarda las credenciales del usuario de servicio en `/home/ubuntu/consumer-alertas.env`, fuera del repositorio:

```
API_USUARIO=<usuario de servicio>
API_PASSWORD=<su contraseña>
```

```bash
chmod 600 /home/ubuntu/consumer-alertas.env
```

En `consumer-alertas.service`, cambia `API_URL` por la URL del backend (el DNS del ALB). Después, instala y arranca el servicio:

```bash
sudo cp data-platform/processing/streaming/consumer-alertas.service /etc/systemd/system/
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now consumer-alertas
```

Revisa que esté procesando alertas:

```bash
tail -f ~/consumer_alertas.log
```

Para probarlo de punta a punta, simula un ataque con `scripts/demo_trafico.py --prueba-tarjetas`.

## Cómo está organizado

```
backend/
  config/          Settings y URLs
  usuarios/        Usuario, Asociado, Comercio, login y permisos por rol; comando cargar_datos
  tarjetas/        Tarjeta, Bloqueo y hash del CVV
  autorizaciones/  Autorizacion, el autorizador (servicios.py) y el acceso al modelo (modelo.py)
  alertas/         Alerta
  portal/          Reclamo y los endpoints del asociado
  eventos/         El log de negocio
frontend/src/
  app/             Arranque, router y guardias por rol
  features/        auth, comercio, portal y consola: vistas, servicios y rutas de cada módulo
  shared/          Componentes, cliente HTTP y utilidades
scripts/           Tráfico de demo
docs/              Formato de carga de datos
```

En cada app, las vistas solo traducen HTTP: las reglas de negocio están en `servicios.py`.

## Log de eventos

Cada operación escribe una línea JSON en `/var/log/coopandina/eventos.log`, solo después de confirmar la transacción. En local queda en `logs/eventos.log`. Rota a diario y conserva 30 días.

```bash
tail -f logs/eventos.log
```

Nunca se registran el número completo de la tarjeta, el CVV, las contraseñas ni los valores de los datos personales que cambian.

## Decisiones que complementan la especificación

- **CVV con HMAC-SHA256 y llave del servidor**, no con el hash de contraseñas de Django: se calcula con la fila de la tarjeta bloqueada, así que no puede tardar cientos de milisegundos. Lo protege la llave `CVV_HMAC_KEY`, que no está en la base de datos.
- **Gunicorn con un worker y varios hilos**: `TimedRotatingFileHandler` no es seguro entre procesos, y varios workers podrían perder eventos al rotar.
- **La tarjeta se busca antes de la validación 1** aunque se valide en el paso 3: si existe, un rechazo por comercio bloqueado también debe guardarse.
- **Un rechazo responde HTTP 200**: es una decisión de negocio. Un 400 significa que la petición está mal formada, y esas no generan evento.
- **`fecha_vencimiento` se envía como `MM/AA`**, como aparece en la tarjeta.
- **Un solo bloqueo vigente por tarjeta o comercio**, con restricción en la base de datos. Bloquear algo ya bloqueado responde 409.
- **Una compra admite un solo reclamo.**
- **Endpoints agregados** porque las pantallas los necesitan: `GET /api/asociado/perfil/` y `GET /api/bloqueos/`.
- **`INICIO_SESION` fallido** registra `USUARIO_INEXISTENTE`, `USUARIO_INACTIVO` o `CONTRASENA_INVALIDA`. El cliente siempre recibe el mismo error.

Lo que queda fuera de alcance está en la especificación: pagos, PIN, 3-D Secure, notificaciones y detección de patrones en conjunto, entre otros.
