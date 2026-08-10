#!/usr/bin/env bash

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${DEPLOY_VENV_DIR:-$APP_DIR/.venv}"
PYTHON_BIN="${DEPLOY_PYTHON_BIN:-python3}"
SERVICE_NAME_RAW="${DEPLOY_SERVICE:-plataforma-elemental}"
ENV_FILE="${DEPLOY_ENV_FILE:-}"
EXPECTED_COMMIT="${DEPLOY_EXPECTED_COMMIT:-}"
PREVIOUS_COMMIT="${DEPLOY_PREVIOUS_COMMIT:-}"
ALLOW_FULL_MIGRATE="${DEPLOY_ALLOW_FULL_MIGRATE:-}"
BACKUP_DIR="${DEPLOY_BACKUP_DIR:-}"

if [[ "$SERVICE_NAME_RAW" == *.service ]]; then
  SERVICE_NAME="${SERVICE_NAME_RAW%.service}"
else
  SERVICE_NAME="$SERVICE_NAME_RAW"
fi

SERVICE_UNIT="${SERVICE_NAME}.service"

cd "$APP_DIR"

if [[ ! -f "$APP_DIR/manage.py" ]]; then
  echo "No existe manage.py en APP_DIR: $APP_DIR" >&2
  exit 1
fi

if [[ -z "$ENV_FILE" ]]; then
  echo "DEPLOY_ENV_FILE es obligatorio para deploy productivo." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "No existe el archivo de entorno: $ENV_FILE" >&2
  exit 1
fi

if [[ ! "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "DEPLOY_EXPECTED_COMMIT debe ser un hash Git completo." >&2
  exit 1
fi
if [[ "$(git rev-parse HEAD)" != "$EXPECTED_COMMIT" ]]; then
  echo "El checkout no coincide con DEPLOY_EXPECTED_COMMIT." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "El checkout de despliegue contiene cambios locales." >&2
  exit 1
fi
if [[ "$ALLOW_FULL_MIGRATE" != "FULL_MIGRATE_APPROVED" ]]; then
  echo "El deploy automático exige aprobación literal de migrate completo." >&2
  echo "Para migraciones por etapas use el runbook específico de la liberación." >&2
  exit 1
fi
if [[ ! "$PREVIOUS_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "DEPLOY_PREVIOUS_COMMIT debe registrar el hash productivo anterior." >&2
  exit 1
fi
if [[ "$BACKUP_DIR" != /* ]] || [[ ! -d "$BACKUP_DIR" ]] || [[ ! -w "$BACKUP_DIR" ]]; then
  echo "DEPLOY_BACKUP_DIR debe ser un directorio absoluto, existente y escribible." >&2
  exit 1
fi
case "$(realpath "$BACKUP_DIR")/" in
  "$(realpath "$APP_DIR")/"*)
    echo "DEPLOY_BACKUP_DIR debe quedar fuera del checkout de aplicación." >&2
    exit 1
    ;;
esac

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

validate_prod_environment() {
  : "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD para deploy productivo}"

  if [[ "${DJANGO_ENV:-}" != "prod" ]]; then
    echo "DJANGO_ENV debe ser prod para deploy productivo." >&2
    exit 1
  fi
  if [[ "${POSTGRES_DB:-}" != "plataforma_elemental_prod" ]]; then
    echo "POSTGRES_DB no corresponde a la base productiva esperada." >&2
    exit 1
  fi
  if [[ "${POSTGRES_USER:-}" != "elementos" ]]; then
    echo "POSTGRES_USER no corresponde al usuario productivo esperado." >&2
    exit 1
  fi
  if [[ "${POSTGRES_HOST:-}" != "127.0.0.1" ]]; then
    echo "POSTGRES_HOST no corresponde al host productivo esperado." >&2
    exit 1
  fi
  if [[ "${POSTGRES_PORT:-}" != "5432" ]]; then
    echo "POSTGRES_PORT no corresponde al puerto productivo esperado." >&2
    exit 1
  fi
}

backup_postgresql_prod() {
  if [[ "$DJANGO_ENV" != "prod" ]]; then
    return 0
  fi

  : "${POSTGRES_DB:?Falta POSTGRES_DB para backup PostgreSQL}"
  : "${POSTGRES_USER:?Falta POSTGRES_USER para backup PostgreSQL}"
  : "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD para backup PostgreSQL}"
  : "${POSTGRES_HOST:?Falta POSTGRES_HOST para backup PostgreSQL}"
  : "${POSTGRES_PORT:?Falta POSTGRES_PORT para backup PostgreSQL}"

  local backup_dir timestamp commit_short backup_file
  backup_dir="$BACKUP_DIR"
  timestamp="$(date +%Y%m%d_%H%M%S)"
  commit_short="$(git rev-parse --short HEAD)"
  backup_file="${backup_dir}/${POSTGRES_DB}_${timestamp}_${commit_short}.dump"

  echo "Creando backup PostgreSQL previo a migraciones: ${backup_file}"

  PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    --host "$POSTGRES_HOST" \
    --port "$POSTGRES_PORT" \
    --username "$POSTGRES_USER" \
    --format custom \
    --no-owner \
    --no-acl \
    --file "$backup_file" \
    "$POSTGRES_DB"
}

if [[ ! -d "$VENV_DIR" ]] || [[ ! -x "$VENV_DIR/bin/python" ]]; then
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

validate_prod_environment
backup_postgresql_prod
python manage.py migrate --noinput
python manage.py clearsessions
python manage.py collectstatic --noinput
python manage.py check --deploy

if [[ "$(systemctl show "$SERVICE_UNIT" --property LoadState --value 2>/dev/null || true)" == "not-found" ]]; then
  echo "No existe el servicio systemd: ${SERVICE_UNIT}" >&2
  exit 1
fi

systemctl restart "$SERVICE_UNIT"
systemctl is-active --quiet "$SERVICE_UNIT"

echo "Deploy completado en el commit $(git rev-parse --short HEAD)"
