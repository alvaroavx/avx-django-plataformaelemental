#!/usr/bin/env bash

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${DEPLOY_VENV_DIR:-$APP_DIR/.venv}"
ENV_FILE="${DEPLOY_ENV_FILE:-}"

fail() {
  echo "SMOKE ERROR: $*" >&2
  exit 1
}

[[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] || fail "DEPLOY_ENV_FILE no existe."
[[ -x "$VENV_DIR/bin/python" ]] || fail "No existe el Python del virtualenv productivo."

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

[[ "${DJANGO_ENV:-}" == "prod" ]] || fail "DJANGO_ENV debe ser prod."
: "${DEPLOY_SMOKE_BASE_URL:?Falta DEPLOY_SMOKE_BASE_URL}"
: "${DEPLOY_SMOKE_HOST:?Falta DEPLOY_SMOKE_HOST}"
: "${DEPLOY_SMOKE_PROFESOR_USERNAME:?Falta DEPLOY_SMOKE_PROFESOR_USERNAME}"
: "${DEPLOY_SMOKE_PROFESOR_ORG_ID:?Falta DEPLOY_SMOKE_PROFESOR_ORG_ID}"
: "${DEPLOY_SMOKE_FOREIGN_ORG_ID:?Falta DEPLOY_SMOKE_FOREIGN_ORG_ID}"

[[ "$DEPLOY_SMOKE_PROFESOR_ORG_ID" =~ ^[0-9]+$ ]] \
  || fail "DEPLOY_SMOKE_PROFESOR_ORG_ID debe ser numérico."
[[ "$DEPLOY_SMOKE_FOREIGN_ORG_ID" =~ ^[0-9]+$ ]] \
  || fail "DEPLOY_SMOKE_FOREIGN_ORG_ID debe ser numérico."
[[ "$DEPLOY_SMOKE_PROFESOR_ORG_ID" != "$DEPLOY_SMOKE_FOREIGN_ORG_ID" ]] \
  || fail "Las organizaciones de smoke deben ser distintas."
[[ "$DEPLOY_SMOKE_HOST" != *"://"* && "$DEPLOY_SMOKE_HOST" != */* ]] \
  || fail "DEPLOY_SMOKE_HOST debe contener solo el host."

BASE_URL="${DEPLOY_SMOKE_BASE_URL%/}"
[[ "$BASE_URL" == "https://$DEPLOY_SMOKE_HOST" ]] \
  || fail "DEPLOY_SMOKE_BASE_URL debe ser https://DEPLOY_SMOKE_HOST sin ruta."
home_result="$(curl --silent --show-error --max-time 20 --output /dev/null \
  --retry 5 --retry-delay 2 --retry-all-errors \
  --write-out '%{http_code}|%{redirect_url}' "$BASE_URL/")"
home_status="${home_result%%|*}"
home_redirect="${home_result#*|}"
[[ "$home_status" == "302" ]] || fail "/ respondió $home_status; se esperaba 302."
[[ "$home_redirect" == *"/accounts/login/"* ]] \
  || fail "/ no redirigió a /accounts/login/."
echo "SMOKE OK: / -> 302 a login"

login_status="$(curl --silent --show-error --max-time 20 --output /dev/null \
  --retry 5 --retry-delay 2 --retry-all-errors \
  --write-out '%{http_code}' "$BASE_URL/accounts/login/")"
[[ "$login_status" == "200" ]] \
  || fail "/accounts/login/ respondió $login_status; se esperaba 200."
echo "SMOKE OK: /accounts/login/ -> 200"

cd "$APP_DIR"
"$VENV_DIR/bin/python" manage.py verificar_smoke_profesor \
  --username "$DEPLOY_SMOKE_PROFESOR_USERNAME" \
  --organizacion-id "$DEPLOY_SMOKE_PROFESOR_ORG_ID" \
  --organizacion-ajena-id "$DEPLOY_SMOKE_FOREIGN_ORG_ID" \
  --host "$DEPLOY_SMOKE_HOST"

echo "SMOKE OK: Profesor autorizado=200 y organización ajena=404"
