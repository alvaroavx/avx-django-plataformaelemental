#!/usr/bin/env bash

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${DEPLOY_VENV_DIR:-$APP_DIR/.venv}"
PYTHON_BIN="${DEPLOY_PYTHON_BIN:-python3}"
SERVICE_NAME_RAW="${DEPLOY_SERVICE:-plataforma-elemental}"
ENV_FILE="${DEPLOY_ENV_FILE:-}"
EXPECTED_COMMIT="${DEPLOY_EXPECTED_COMMIT:-}"
PREVIOUS_COMMIT="${DEPLOY_PREVIOUS_COMMIT:-}"
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
if [[ ! "$PREVIOUS_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "DEPLOY_PREVIOUS_COMMIT debe registrar el hash productivo anterior." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
BACKUP_DIR="${DEPLOY_BACKUP_DIR:-$BACKUP_DIR}"

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

validate_service() {
  if [[ "$(systemctl show "$SERVICE_UNIT" --property LoadState --value 2>/dev/null || true)" == "not-found" ]]; then
    echo "No existe el servicio systemd: ${SERVICE_UNIT}" >&2
    exit 1
  fi
}

validate_backup_destination() {
  if [[ -z "$BACKUP_DIR" ]]; then
    echo "DEPLOY_BACKUP_DIR es obligatorio cuando existen migraciones pendientes." >&2
    exit 1
  fi
  if [[ "$BACKUP_DIR" != /* || "$BACKUP_DIR" == /tmp || "$BACKUP_DIR" == /tmp/* ]]; then
    echo "DEPLOY_BACKUP_DIR debe ser una ruta absoluta y persistente fuera de /tmp." >&2
    exit 1
  fi
  case "$BACKUP_DIR/" in
    "$APP_DIR"/*)
      echo "DEPLOY_BACKUP_DIR no puede estar dentro del checkout productivo." >&2
      exit 1
      ;;
  esac
  if [[ ! -d "$BACKUP_DIR" || ! -w "$BACKUP_DIR" ]]; then
    echo "DEPLOY_BACKUP_DIR no existe o no permite escritura: $BACKUP_DIR" >&2
    exit 1
  fi
  command -v pg_dump >/dev/null
  command -v pg_restore >/dev/null
}

backup_database() {
  local timestamp short_commit backup_file

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  short_commit="$(git rev-parse --short=12 HEAD)"
  backup_file="$BACKUP_DIR/plataforma-elemental-${timestamp}-${short_commit}.dump"

  PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    --host "$POSTGRES_HOST" \
    --port "$POSTGRES_PORT" \
    --username "$POSTGRES_USER" \
    --format=custom \
    --no-owner \
    --no-acl \
    --file "$backup_file" \
    "$POSTGRES_DB"
  pg_restore --list "$backup_file" >/dev/null
  sha256sum "$backup_file" > "${backup_file}.sha256"
  echo "Backup PostgreSQL validado antes de migrar: $backup_file"
}

publish_static_files() {
  local static_root expected_static_root

  static_root="$(DJANGO_SETTINGS_MODULE=plataformaelemental.config python -c \
    'from django.conf import settings; print(settings.STATIC_ROOT)')"
  expected_static_root="$APP_DIR/plataformaelemental/staticfiles"

  if [[ "$static_root" != "$expected_static_root" ]]; then
    echo "STATIC_ROOT inesperado: $static_root" >&2
    exit 1
  fi

  python manage.py collectstatic --noinput

  # Nginx sirve STATIC_ROOT directamente y necesita atravesar directorios y
  # leer archivos de todas las apps. collectstatic no corrige necesariamente
  # modos restrictivos heredados de ejecuciones anteriores.
  find "$static_root" -type d -exec chmod 755 {} +
  find "$static_root" -type f -exec chmod 644 {} +

  for required_static in \
    "$static_root/asistencias/css/profesor.css" \
    "$static_root/asistencias/js/profesor_contexto.js" \
    "$static_root/admin/css/base.css" \
    "$static_root/staticfiles.json"; do
    if [[ ! -f "$required_static" || ! -r "$required_static" ]]; then
      echo "Falta un estático obligatorio o no permite lectura: $required_static" >&2
      exit 1
    fi
  done
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
python manage.py makemigrations --check --dry-run
validate_service
python manage.py showmigrations --plan >/dev/null

if python manage.py migrate --check; then
  echo "No hay migraciones pendientes."
else
  if python manage.py showmigrations asistencias --list \
    | grep -Eq '^\[ \].*(0004b_reparar_precondiciones_0005|0005_reparar_schema_0004_aplicada_precommit_v2|0006_merge_0004b_y_0005|0007_reconciliar_relaciones_activas)'; then
    echo "La reparación histórica de Operación Profesor sigue pendiente; use el runbook escalonado." >&2
    exit 1
  fi

  validate_backup_destination
  echo "Hay migraciones pendientes; se detendrá la aplicación antes del respaldo y la migración."
  systemctl stop "$SERVICE_UNIT"
  if ! backup_database; then
    echo "Falló el respaldo; el servicio permanece detenido para evitar escrituras sin cobertura." >&2
    exit 1
  fi
  if ! python manage.py migrate --noinput; then
    echo "Falló la migración; el servicio permanece detenido y requiere recuperación forward-only." >&2
    exit 1
  fi
fi

python manage.py migrate --check
python manage.py clearsessions
publish_static_files
python manage.py check --deploy

systemctl restart "$SERVICE_UNIT"
systemctl is-active --quiet "$SERVICE_UNIT"

echo "Deploy completado en el commit $(git rev-parse --short HEAD)"
