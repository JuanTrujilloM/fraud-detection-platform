#!/usr/bin/env bash
# Simula la entrega semanal de la red: genera el archivo de contracargos y lo deja en el buzón de S3.
# Uso: bash scripts/entregar_contracargos.sh [AAAA-MM-DD]   (lunes de la entrega; opcional)
set -euo pipefail

cd "$(dirname "$0")/.."
BUCKET="${BUCKET:-datalake-fraudwatch}"
FECHA="${1:-}"

docker compose -f docker-compose.prod.yml exec -T backend \
  python manage.py generar_contracargos --salida /exports ${FECHA:+--semana-hasta "$FECHA"}

mkdir -p exports/enviados
for archivo in exports/contracargos_*.csv; do
  [ -e "$archivo" ] || continue
  aws s3 cp "$archivo" "s3://$BUCKET/landing/contracargos/"
  mv "$archivo" exports/enviados/
done
