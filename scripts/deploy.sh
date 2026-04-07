#!/usr/bin/env bash

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Variables opcionales:
# - DEPLOY_VENV_DIR: permite usar un virtualenv fuera del repo
# - DEPLOY_PYTHON_BIN: permite elegir el binario base para crear el virtualenv
# - DEPLOY_ENV_FILE: permite cargar un archivo de entorno explicito en el servidor
# Variable requerida en la practica:
# - DEPLOY_SERVICE: si no se define, usa `plataforma-elemental`
VENV_DIR="${DEPLOY_VENV_DIR:-$APP_DIR/.venv}"
PYTHON_BIN="${DEPLOY_PYTHON_BIN:-python3}"
SERVICE_NAME="${DEPLOY_SERVICE:-plataforma-elemental}"
ENV_FILE="${DEPLOY_ENV_FILE:-}"

cd "$APP_DIR"

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "No existe el archivo de entorno: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export DJANGO_ENV="${DJANGO_ENV:-prod}"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check

if ! systemctl list-unit-files | grep -q "^${SERVICE_NAME}\.service"; then
  echo "No existe el servicio systemd: ${SERVICE_NAME}.service" >&2
  exit 1
fi

sudo systemctl restart "$SERVICE_NAME"
sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "Deploy completado en el commit $(git rev-parse --short HEAD)"