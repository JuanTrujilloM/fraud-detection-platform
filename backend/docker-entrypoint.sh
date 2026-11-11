#!/bin/sh
set -e
python manage.py check
python manage.py migrate --noinput

# Un solo worker con hilos: el log de eventos rota con TimedRotatingFileHandler, que no es seguro
# entre procesos. Varios workers podrían perder eventos al rotar a medianoche.
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 1 \
  --threads "${GUNICORN_THREADS:-8}" \
  --access-logfile -
