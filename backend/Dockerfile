FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    EVENTOS_LOG_PATH=/var/log/coopandina/eventos.log

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN useradd --uid 1000 --create-home app \
    && mkdir -p /var/log/coopandina \
    && chown app:app /var/log/coopandina

RUN uv sync --frozen
COPY . .
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput
USER app
CMD ["./docker-entrypoint.sh"]
