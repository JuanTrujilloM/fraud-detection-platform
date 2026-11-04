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

En otra terminal, carga los datos de muestra (usa la `CARGA_PASSWORD` de tu `.env` como contraseña de todos los usuarios):

```bash
docker compose exec backend python manage.py cargar_datos
```

Entra a <http://localhost:5173>:

| Rol | Usuario | Módulo |
| --- | --- | --- |
| Comercio con tienda en línea | `comercio_900100006` | Terminal de pago |
| Comercio solo presencial | `comercio_900100001` | Terminal de pago |
| Asociado | `asociado_1000000001` | Portal |
| Analista | `analista_demo` | Consola de fraude |
| Administrador | `admin_demo` | [Admin de Django](http://localhost:5173/admin/) |

Las tarjetas de prueba están en [`backend/data/muestra/tarjetas.csv`](backend/data/muestra/tarjetas.csv), con su CVV en claro porque son sintéticas.

Para generar tráfico:

```bash
python3 scripts/demo_trafico.py --password <CARGA_PASSWORD> --compras 200
```

El script también tiene `--prueba-tarjetas`, que simula el ataque que debe detectar el procesamiento en streaming.

El modelo de ML todavía devuelve un valor fijo bajo, así que no aparecerán alertas. Para verlas, sube `MODELO_PROBABILIDAD_FIJA` en `.env` (por ejemplo a `0.7` para aprobar con alerta o a `0.9` para rechazar) y recrea el contenedor:

```bash
docker compose up -d --force-recreate backend
```

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
scripts/           Generador de la muestra y tráfico de demo
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
