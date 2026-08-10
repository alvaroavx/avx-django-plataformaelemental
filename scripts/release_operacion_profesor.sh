#!/usr/bin/env bash

set -euo pipefail
umask 077

EXPECTED_RELEASE_TAG="release/operacion-profesor-20260810.1"
EXPECTED_PARENT_COMMIT="c47ce8225b3221b28a00baf9a4d2909e154c3b30"
MANUAL_RELEASE_ONLY=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${DEPLOY_VENV_DIR:-$APP_DIR/.venv}"
ENV_FILE="${DEPLOY_ENV_FILE:-}"
SERVICE_NAME_RAW="${DEPLOY_SERVICE:-plataforma-elemental}"
OPS_DIR="${RELEASE_OPS_DIR:-}"
ACTION="${1:-}"

if [[ "$SERVICE_NAME_RAW" == *.service ]]; then
  SERVICE_UNIT="$SERVICE_NAME_RAW"
else
  SERVICE_UNIT="${SERVICE_NAME_RAW}.service"
fi

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Uso:
  scripts/release_operacion_profesor.sh verify-release
  scripts/release_operacion_profesor.sh install
  scripts/release_operacion_profesor.sh plan-before
  scripts/release_operacion_profesor.sh migrate-asistencias
  scripts/release_operacion_profesor.sh report
  scripts/release_operacion_profesor.sh confirm-activations
  scripts/release_operacion_profesor.sh migrate-finanzas
  scripts/release_operacion_profesor.sh finalize

Variables requeridas:
  DEPLOY_ENV_FILE   EnvironmentFile productivo existente.
  RELEASE_OPS_DIR   Directorio protegido para planes, reportes y tiempos.
  PROD_PREV_COMMIT  Hash real registrado antes de cambiar el checkout.

Confirmación de la revisión administrativa:
  RELEASE_ACTIVATION_ACTOR=<usuario administrador>
  RELEASE_CONFIRM_ACTIVACIONES=RELACIONES_VIGENTES_REVISADAS

Confirmación adicional para migrate-finanzas:
  RELEASE_CONFIRM_FINANZAS=APLICAR_FINANZAS_0012

Este script no crea backups, no activa relaciones, no inicia servicios y no
ejecuta migrate completo. Seguir el runbook en todos los pasos intermedios.
USAGE
}

[[ -n "$ACTION" ]] || { usage; exit 2; }
case "$ACTION" in
  -h|--help|help)
    usage
    exit 0
    ;;
esac
[[ -f "$APP_DIR/manage.py" ]] || fail "No existe manage.py en $APP_DIR."
cd "$APP_DIR"
[[ -z "$(git status --porcelain)" ]] || fail "El worktree no está limpio."
HEAD_COMMIT="$(git rev-parse HEAD)"
PARENT_COMMIT="$(git rev-parse HEAD^)"
[[ "$(git cat-file -t "refs/tags/${EXPECTED_RELEASE_TAG}" 2>/dev/null)" == "tag" ]] \
  || fail "${EXPECTED_RELEASE_TAG} debe ser un tag anotado."
TAG_COMMIT="$(git rev-parse "refs/tags/${EXPECTED_RELEASE_TAG}^{commit}" 2>/dev/null)" \
  || fail "No existe el tag esperado ${EXPECTED_RELEASE_TAG}."
[[ "$TAG_COMMIT" == "$HEAD_COMMIT" ]] \
  || fail "HEAD no coincide con el SHA esperado por ${EXPECTED_RELEASE_TAG}."
[[ "$PARENT_COMMIT" == "$EXPECTED_PARENT_COMMIT" ]] \
  || fail "El release no es el segundo commit esperado sobre c47ce822."

if [[ "$ACTION" == "verify-release" ]]; then
  printf 'Release verificado: %s -> %s\n' "$EXPECTED_RELEASE_TAG" "$HEAD_COMMIT"
  exit 0
fi

[[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] || fail "DEPLOY_ENV_FILE no existe."
[[ -n "$OPS_DIR" && "$OPS_DIR" == /* ]] || fail "RELEASE_OPS_DIR debe ser absoluto."
mkdir -p "$OPS_DIR"
case "$(realpath "$OPS_DIR")/" in
  "$APP_DIR/"*) fail "RELEASE_OPS_DIR debe quedar fuera del checkout." ;;
esac
[[ -x "$VENV_DIR/bin/python" ]] || fail "No existe el virtualenv productivo."
[[ "${PROD_PREV_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]] || fail "PROD_PREV_COMMIT no es válido."
[[ "$PROD_PREV_COMMIT" != "$HEAD_COMMIT" ]] || fail "El hash previo no puede ser el release."

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
[[ "${DJANGO_ENV:-}" == "prod" ]] || fail "DJANGO_ENV debe ser prod."
export PGOPTIONS="-c lock_timeout=5s -c statement_timeout=15min"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

plan_path() {
  local label="$1"
  python manage.py showmigrations --plan | tee "$OPS_DIR/showmigrations-${label}.txt"
}

pending_migrations() {
  python manage.py showmigrations --plan | sed -n 's/^\[ \][[:space:]]*//p' | sort
}

assert_pending() {
  local expected actual
  expected="$(printf '%s\n' "$@" | sed '/^$/d' | sort)"
  actual="$(pending_migrations)"
  if [[ "$actual" != "$expected" ]]; then
    echo "Migraciones pendientes esperadas:" >&2
    printf '%s\n' "$expected" >&2
    echo "Migraciones pendientes reales:" >&2
    printf '%s\n' "$actual" >&2
    fail "El plan contiene migraciones inesperadas."
  fi
}

require_maintenance() {
  local state
  state="$(systemctl is-active "$SERVICE_UNIT" 2>/dev/null || true)"
  [[ "$state" != "active" ]] || fail "El servicio sigue activo; habilite mantenimiento."
}

REPORT_MARKER="$OPS_DIR/gate-${HEAD_COMMIT}-reporte-completo.txt"
ACTIVATION_MARKER="$OPS_DIR/gate-${HEAD_COMMIT}-activaciones-revisadas.txt"

marker_matches_release() {
  local marker="$1"
  [[ -f "$marker" ]] && grep -Fqx "release_commit=$HEAD_COMMIT" "$marker"
}

write_report() {
  local report_date report_stamp
  report_date="${RELEASE_REPORT_DATE:-$(date +%F)}"
  report_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  python manage.py reportar_relaciones_historicas \
    --fecha-corte "$report_date" --dias-vigencia-alumno 90 \
    --formato=json --fallar-si-inseguro \
    > "$OPS_DIR/relaciones-${report_stamp}-sanitizado.json"
  python manage.py reportar_relaciones_historicas \
    --fecha-corte "$report_date" --dias-vigencia-alumno 90 \
    --formato=json --fallar-si-inseguro --incluir-detalle-operativo \
    > "$OPS_DIR/relaciones-${report_stamp}-protegido.json"
}

case "$ACTION" in
  install)
    python -m pip install --requirement requirements.txt
    python manage.py check --deploy
    ;;
  plan-before)
    require_maintenance
    assert_pending \
      "asistencias.0004_alter_sesionclase_estado_liberacionsesion_and_more" \
      "finanzas.0012_payment_clave_idempotencia_payment_disciplina_and_more"
    plan_path before
    python manage.py showmigrations --plan asistencias \
      | tee "$OPS_DIR/showmigrations-asistencias-before.txt"
    ;;
  migrate-asistencias)
    require_maintenance
    assert_pending \
      "asistencias.0004_alter_sesionclase_estado_liberacionsesion_and_more" \
      "finanzas.0012_payment_clave_idempotencia_payment_disciplina_and_more"
    plan_path before-asistencias
    /usr/bin/time -p python manage.py migrate asistencias 0004 --noinput \
      2>&1 | tee "$OPS_DIR/migrate-asistencias-0004.txt"
    assert_pending "finanzas.0012_payment_clave_idempotencia_payment_disciplina_and_more"
    plan_path after-asistencias
    ;;
  report)
    require_maintenance
    assert_pending "finanzas.0012_payment_clave_idempotencia_payment_disciplina_and_more"
    write_report
    printf 'release_tag=%s\nrelease_commit=%s\nreported_at=%s\n' \
      "$EXPECTED_RELEASE_TAG" "$HEAD_COMMIT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$REPORT_MARKER"
    ;;
  confirm-activations)
    require_maintenance
    assert_pending "finanzas.0012_payment_clave_idempotencia_payment_disciplina_and_more"
    marker_matches_release "$REPORT_MARKER" \
      || fail "Primero debe ejecutar y conservar el reporte de relaciones."
    [[ -n "${RELEASE_ACTIVATION_ACTOR:-}" ]] \
      || fail "Falta RELEASE_ACTIVATION_ACTOR."
    [[ "${RELEASE_CONFIRM_ACTIVACIONES:-}" == "RELACIONES_VIGENTES_REVISADAS" ]] \
      || fail "Falta la confirmación literal de activaciones revisadas."
    write_report
    printf 'release_tag=%s\nrelease_commit=%s\nactor=%s\nconfirmed_at=%s\n' \
      "$EXPECTED_RELEASE_TAG" "$HEAD_COMMIT" "$RELEASE_ACTIVATION_ACTOR" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ACTIVATION_MARKER"
    ;;
  migrate-finanzas)
    require_maintenance
    marker_matches_release "$REPORT_MARKER" \
      || fail "Falta el gate de reporte para este release."
    marker_matches_release "$ACTIVATION_MARKER" \
      || fail "Falta el gate de activación administrativa revisada."
    [[ "${RELEASE_CONFIRM_FINANZAS:-}" == "APLICAR_FINANZAS_0012" ]] \
      || fail "Falta RELEASE_CONFIRM_FINANZAS=APLICAR_FINANZAS_0012."
    assert_pending "finanzas.0012_payment_clave_idempotencia_payment_disciplina_and_more"
    plan_path before-finanzas
    python manage.py showmigrations --plan finanzas \
      | tee "$OPS_DIR/showmigrations-finanzas-before.txt"
    /usr/bin/time -p python manage.py migrate finanzas 0012 --noinput \
      2>&1 | tee "$OPS_DIR/migrate-finanzas-0012.txt"
    assert_pending
    plan_path after-finanzas
    ;;
  finalize)
    require_maintenance
    assert_pending
    python manage.py migrate --check
    python manage.py collectstatic --noinput
    python manage.py check --deploy
    plan_path final
    ;;
  *)
    usage
    fail "Acción desconocida: $ACTION"
    ;;
esac
