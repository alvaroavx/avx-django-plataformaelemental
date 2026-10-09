#!/usr/bin/env bash

set -euo pipefail

ENV_FILE="${DEPLOY_ENV_FILE:-}"

fail() {
  echo "SMOKE ERROR: $*" >&2
  exit 1
}

[[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] || fail "DEPLOY_ENV_FILE no existe."
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

[[ "${DJANGO_ENV:-}" == "prod" ]] || fail "DJANGO_ENV debe ser prod."
: "${DEPLOY_SMOKE_BASE_URL:?Falta DEPLOY_SMOKE_BASE_URL}"
: "${DEPLOY_SMOKE_HOST:?Falta DEPLOY_SMOKE_HOST}"
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
