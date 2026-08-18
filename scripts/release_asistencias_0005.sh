#!/usr/bin/env bash

set -euo pipefail
umask 077

EXPECTED_RELEASE_TAG="release/asistencias-0005-20260818.1"
EXPECTED_PARENT_COMMIT="4b687d109315e71391d840a1881d808fcc7e428d"
MANUAL_RELEASE_ONLY=1

ACTION="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$ACTION" == "verify-release" && -n "${RELEASE_REPO_DIR:-}" ]]; then
  APP_DIR="$(realpath "$RELEASE_REPO_DIR")"
else
  APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
VENV_DIR="${DEPLOY_VENV_DIR:-$APP_DIR/.venv}"
ENV_FILE="${DEPLOY_ENV_FILE:-}"
OPS_DIR="${RELEASE_OPS_DIR:-}"
BACKUP_FILE="${RELEASE_BACKUP_FILE:-}"
SERVICE_NAME_RAW="${DEPLOY_SERVICE:-plataforma-elemental}"

if [[ "$SERVICE_NAME_RAW" == *.service ]]; then
  SERVICE_UNIT="$SERVICE_NAME_RAW"
else
  SERVICE_UNIT="${SERVICE_NAME_RAW}.service"
fi

fail() {
  echo "ERROR RELEASE 0005: $*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Uso:
  scripts/release_asistencias_0005.sh self-test
  scripts/release_asistencias_0005.sh verify-release
  scripts/release_asistencias_0005.sh install
  scripts/release_asistencias_0005.sh preflight
  scripts/release_asistencias_0005.sh route-a-migrate-0005
  scripts/release_asistencias_0005.sh route-b-migrate-0004
  scripts/release_asistencias_0005.sh route-b-migrate-0005
  scripts/release_asistencias_0005.sh report
  scripts/release_asistencias_0005.sh confirm-activations
  scripts/release_asistencias_0005.sh route-b-migrate-finanzas
  scripts/release_asistencias_0005.sh diagnose-0005
  scripts/release_asistencias_0005.sh finalize

Identidad obligatoria:
  RELEASE_EXPECTED_COMMIT=<SHA completo entregado con el release>
  RELEASE_REPO_DIR=<checkout productivo actual; solo para verify-release por stdin>

Variables operativas obligatorias desde preflight:
  DEPLOY_ENV_FILE=<environment file productivo>
  RELEASE_OPS_DIR=<directorio protegido fuera del checkout>
  RELEASE_BACKUP_FILE=<dump custom previo, fuera del checkout y de /tmp>
  RELEASE_BACKUP_STORAGE_CONFIRMED=EXTERNO_SEGURO_VERIFICADO
  RELEASE_BACKUP_RESTORE_CONFIRMED=RESTAURACION_VERIFICADA
  RELEASE_SNAPSHOT_REFERENCE=<identificador opaco del snapshot previo>
  RELEASE_SNAPSHOT_CONFIRMED=SNAPSHOT_PREVIO_VERIFICADO

Confirmaciones de escritura:
  RELEASE_CONFIRM_0005=APLICAR_ASISTENCIAS_0005
  RELEASE_CONFIRM_0004=APLICAR_ASISTENCIAS_0004
  RELEASE_CONFIRM_FINANZAS=APLICAR_FINANZAS_0012

Confirmación administrativa posterior al reporte:
  RELEASE_ACTIVATION_USER_ID=<User.id activo con permisos en el alcance pendiente>
  RELEASE_CONFIRM_ACTIVACIONES=RELACIONES_VIGENTES_REVISADAS

El script nunca crea/restaura backups o snapshots, nunca activa relaciones por
sí solo, nunca ejecuta migrate global y nunca reinicia servicios.
USAGE
}

classify_state_values() {
  local asistencia_0004="$1" asistencia_0005="$2" finanzas_0012="$3"
  case "${asistencia_0004}:${asistencia_0005}:${finanzas_0012}" in
    X:P:X) printf '%s\n' "ROUTE_A_READY" ;;
    P:P:P) printf '%s\n' "ROUTE_B_READY_0004" ;;
    X:P:P) printf '%s\n' "ROUTE_B_READY_0005" ;;
    X:X:P) printf '%s\n' "ROUTE_B_REVIEW" ;;
    X:X:X) printf '%s\n' "COMPLETE" ;;
    *) printf '%s\n' "UNKNOWN" ;;
  esac
}

review_mode_from_count() {
  local count="$1"
  if [[ ! "$count" =~ ^[0-9]+$ ]]; then
    printf '%s\n' INVALID
  elif [[ "$count" == "0" ]]; then
    printf '%s\n' NONE
  else
    printf '%s\n' REQUIRED
  fi
}

self_test() {
  [[ "$(classify_state_values X P X)" == "ROUTE_A_READY" ]]
  [[ "$(classify_state_values P P P)" == "ROUTE_B_READY_0004" ]]
  [[ "$(classify_state_values X P P)" == "ROUTE_B_READY_0005" ]]
  [[ "$(classify_state_values X X P)" == "ROUTE_B_REVIEW" ]]
  [[ "$(classify_state_values X X X)" == "COMPLETE" ]]
  [[ "$(classify_state_values P X X)" == "UNKNOWN" ]]
  [[ "$(review_mode_from_count 0)" == "NONE" ]]
  [[ "$(review_mode_from_count 3)" == "REQUIRED" ]]
  [[ "$(review_mode_from_count desconocido)" == "INVALID" ]]
  grep -Fq 'run_timed_migration asistencias-0004 asistencias 0004' "$0"
  grep -Fq 'run_timed_migration asistencias-0005 asistencias 0005' "$0"
  grep -Fq 'run_timed_migration finanzas-0012 finanzas 0012' "$0"
  if grep -Eq 'manage\.py migrate([[:space:]]+--noinput)?[[:space:]]*$' "$0"; then
    fail "El contrato contiene un migrate global."
  fi
  echo "Self-test release 0005: rutas y migraciones explícitas OK"
}

[[ -n "$ACTION" ]] || { usage; exit 2; }
case "$ACTION" in
  -h|--help|help)
    usage
    exit 0
    ;;
  self-test)
    self_test
    exit 0
    ;;
esac

[[ -d "$APP_DIR/.git" || -f "$APP_DIR/.git" ]] || fail "APP_DIR no es un checkout Git."
cd "$APP_DIR"
[[ -z "$(git status --porcelain)" ]] || fail "El worktree no está limpio."

HEAD_COMMIT="$(git rev-parse HEAD)"
EXPECTED_COMMIT="${RELEASE_EXPECTED_COMMIT:-}"
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] \
  || fail "RELEASE_EXPECTED_COMMIT debe ser un SHA completo."
[[ "$(git cat-file -t "refs/tags/${EXPECTED_RELEASE_TAG}" 2>/dev/null)" == "tag" ]] \
  || fail "${EXPECTED_RELEASE_TAG} debe existir como tag anotado."
TAG_COMMIT="$(git rev-parse "refs/tags/${EXPECTED_RELEASE_TAG}^{commit}" 2>/dev/null)" \
  || fail "No se pudo resolver el tag esperado."
[[ "$TAG_COMMIT" == "$EXPECTED_COMMIT" ]] \
  || fail "El tag no resuelve al SHA exacto entregado."
TAG_PARENT="$(git rev-parse "${TAG_COMMIT}^")"
[[ "$TAG_PARENT" == "$EXPECTED_PARENT_COMMIT" ]] \
  || fail "El padre del release no coincide con el padre aprobado."

if [[ "$ACTION" == "verify-release" ]]; then
  [[ "$(systemctl is-active "$SERVICE_UNIT" 2>/dev/null || true)" == "active" ]] \
    || fail "El servicio debe estar activo antes de entrar a mantenimiento."
  printf 'Release verificado sin checkout: tag=%s commit=%s parent=%s production_head=%s service=active\n' \
    "$EXPECTED_RELEASE_TAG" "$TAG_COMMIT" "$TAG_PARENT" "$HEAD_COMMIT"
  exit 0
fi

[[ -f "$APP_DIR/manage.py" ]] || fail "No existe manage.py en $APP_DIR."
[[ "$HEAD_COMMIT" == "$EXPECTED_COMMIT" ]] \
  || fail "HEAD no coincide con RELEASE_EXPECTED_COMMIT."
HEAD_PARENT="$(git rev-parse HEAD^)"
[[ "$HEAD_PARENT" == "$EXPECTED_PARENT_COMMIT" ]] \
  || fail "El padre de HEAD no coincide con el padre aprobado."

[[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] || fail "DEPLOY_ENV_FILE no existe."
[[ -n "$OPS_DIR" && "$OPS_DIR" == /* ]] || fail "RELEASE_OPS_DIR debe ser absoluto."
mkdir -p "$OPS_DIR"
case "$(realpath "$OPS_DIR")/" in
  "$APP_DIR/"*) fail "RELEASE_OPS_DIR debe quedar fuera del checkout." ;;
esac
[[ -x "$VENV_DIR/bin/python" ]] || fail "No existe el Python del virtualenv productivo."

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

[[ "${DJANGO_ENV:-}" == "prod" ]] || fail "DJANGO_ENV debe ser prod."
: "${POSTGRES_DB:?Falta POSTGRES_DB}"
: "${POSTGRES_USER:?Falta POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD}"
: "${POSTGRES_HOST:?Falta POSTGRES_HOST}"
: "${POSTGRES_PORT:?Falta POSTGRES_PORT}"

export PGOPTIONS="-c lock_timeout=5s -c statement_timeout=15min"
DJANGO=("$VENV_DIR/bin/python" manage.py)
PSQL=(
  psql
  --host "$POSTGRES_HOST"
  --port "$POSTGRES_PORT"
  --username "$POSTGRES_USER"
  --dbname "$POSTGRES_DB"
  --no-psqlrc
  --set=ON_ERROR_STOP=1
)

run_psql_readonly() {
  PGPASSWORD="$POSTGRES_PASSWORD" \
    PGOPTIONS="-c default_transaction_read_only=on -c lock_timeout=5s -c statement_timeout=5min" \
    "${PSQL[@]}" "$@"
}

migration_status() {
  local app="$1" migration="$2" output line
  output="$("${DJANGO[@]}" showmigrations "$app" --list)"
  line="$(grep -E "^[[:space:]]*\[[ X]\][[:space:]]+${migration}$" <<<"$output" || true)"
  [[ "$(wc -l <<<"$line")" -eq 1 && -n "$line" ]] \
    || fail "No se pudo resolver el estado de ${app}.${migration}."
  if grep -Eq '^[[:space:]]*\[X\]' <<<"$line"; then
    printf '%s\n' X
  else
    printf '%s\n' P
  fi
}

current_state() {
  local s0004 s0005 f0012
  s0004="$(migration_status asistencias 0004_alter_sesionclase_estado_liberacionsesion_and_more)"
  s0005="$(migration_status asistencias 0005_reparar_schema_0004_aplicada_precommit)"
  f0012="$(migration_status finanzas 0012_payment_clave_idempotencia_payment_disciplina_and_more)"
  classify_state_values "$s0004" "$s0005" "$f0012"
}

require_state() {
  local expected="$1" actual
  actual="$(current_state)"
  [[ "$actual" == "$expected" ]] \
    || fail "Estado de migraciones ${actual}; se esperaba ${expected}."
}

table_exists() {
  local table="$1"
  [[ "$(run_psql_readonly --tuples-only --no-align \
    --command "SELECT to_regclass('public.${table}') IS NOT NULL;")" == "t" ]]
}

column_exists() {
  local table="$1" column="$2"
  [[ "$(run_psql_readonly --tuples-only --no-align --command \
    "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='${table}' AND column_name='${column}');")" == "t" ]]
}

schema_report() {
  local table
  run_psql_readonly <<'SQL'
SELECT version();
SELECT current_database() AS base,
       pg_size_pretty(pg_database_size(current_database())) AS tamano;
SELECT table_name, column_name, data_type, is_nullable, COALESCE(column_default, '') AS valor_por_defecto
  FROM information_schema.columns
 WHERE table_schema = 'public'
   AND table_name IN (
       'asistencias_asignacionprofesordisciplina',
       'asistencias_alumnodisciplina'
   )
   AND column_name IN (
       'activa', 'asignada_por_id', 'origen', 'revisada_en', 'revisada_por_id'
   )
 ORDER BY table_name, ordinal_position;
SQL
  for table in \
    asistencias_asignacionprofesordisciplina \
    asistencias_alumnodisciplina; do
    if table_exists "$table"; then
      run_psql_readonly --command \
        "SELECT '${table}' AS relacion,
                count(*) AS total,
                count(*) FILTER (WHERE activa) AS activas,
                count(*) FILTER (WHERE NOT activa) AS inactivas,
                count(*) FILTER (WHERE asignada_por_id IS NULL)
                    AS sin_actor_explicito_potencialmente_reclasificadas,
                count(*) FILTER (WHERE to_jsonb(r)->>'origen' = 'historica') AS historicas,
                count(*) FILTER (WHERE to_jsonb(r)->>'origen' = 'explicita') AS explicitas
           FROM ${table} AS r;"
    else
      printf 'RELACION_AUSENTE %s\n' "$table"
    fi
  done
}

validate_origin_if_present() {
  local table="$1" metadata invalid
  if ! column_exists "$table" origen; then
    printf 'SCHEMA_PRECOMMIT origen_ausente tabla=%s\n' "$table"
    return 0
  fi
  metadata="$(run_psql_readonly --tuples-only --no-align --field-separator='|' --command \
    "SELECT is_nullable, COALESCE(column_default, '') FROM information_schema.columns WHERE table_schema='public' AND table_name='${table}' AND column_name='origen';")"
  [[ "$metadata" == NO\|*explicita* ]] \
    || fail "${table}.origen existe pero no es NOT NULL con default explicita; 0005 no corrige ese estado parcial."
  invalid="$(run_psql_readonly --tuples-only --no-align --command \
    "SELECT count(*) FROM ${table} WHERE origen IS NULL OR origen NOT IN ('historica', 'explicita');")"
  [[ "$invalid" == "0" ]] \
    || fail "${table}.origen contiene valores nulos o desconocidos; requiere corrección forward revisada."
  printf 'SCHEMA_ORIGEN_VALIDO tabla=%s\n' "$table"
}

validate_schema_before_0005() {
  local state="$1" table column
  if [[ "$state" == "ROUTE_B_READY_0004" ]]; then
    for table in \
      asistencias_asignacionprofesordisciplina \
      asistencias_alumnodisciplina; do
      ! table_exists "$table" \
        || fail "${table} existe aunque 0004 figura pendiente; estado ambiguo."
    done
    return 0
  fi
  for table in \
    asistencias_asignacionprofesordisciplina \
    asistencias_alumnodisciplina; do
    table_exists "$table" || fail "Falta la tabla requerida ${table}."
    for column in activa asignada_por_id; do
      column_exists "$table" "$column" \
        || fail "Falta la columna base ${table}.${column}."
    done
    validate_origin_if_present "$table"
  done
}

validate_schema_after_0005() {
  local table column fk_count index_count
  for table in \
    asistencias_asignacionprofesordisciplina \
    asistencias_alumnodisciplina; do
    table_exists "$table" || fail "Falta la tabla posterior ${table}."
    for column in activa asignada_por_id origen revisada_en revisada_por_id; do
      column_exists "$table" "$column" \
        || fail "0005 quedó aplicada sin ${table}.${column}."
    done
    validate_origin_if_present "$table"
    fk_count="$(run_psql_readonly --tuples-only --no-align --command \
      "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid WHERE t.relname='${table}' AND c.contype='f' AND pg_get_constraintdef(c.oid) LIKE 'FOREIGN KEY (revisada_por_id)%';")"
    [[ "$fk_count" -ge 1 ]] || fail "Falta FK de ${table}.revisada_por_id."
    index_count="$(run_psql_readonly --tuples-only --no-align --command \
      "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='${table}' AND indexdef LIKE '%(revisada_por_id)%';")"
    [[ "$index_count" -ge 1 ]] || fail "Falta índice de ${table}.revisada_por_id."
  done
}

validate_backup() {
  [[ -n "$BACKUP_FILE" && "$BACKUP_FILE" == /* && -s "$BACKUP_FILE" ]] \
    || fail "RELEASE_BACKUP_FILE debe ser un dump absoluto, existente y no vacío."
  case "$(realpath "$BACKUP_FILE")" in
    "$APP_DIR"/*|/tmp/*) fail "El dump no puede estar en el checkout ni en /tmp." ;;
  esac
  [[ "${RELEASE_BACKUP_STORAGE_CONFIRMED:-}" == "EXTERNO_SEGURO_VERIFICADO" ]] \
    || fail "Falta confirmar almacenamiento externo seguro."
  [[ "${RELEASE_BACKUP_RESTORE_CONFIRMED:-}" == "RESTAURACION_VERIFICADA" ]] \
    || fail "Falta confirmar la restauración previa del dump."
  pg_restore --list "$BACKUP_FILE" >/dev/null \
    || fail "pg_restore --list no pudo leer el dump."
  sha256sum "$BACKUP_FILE" | awk '{print $1}'
}

validate_snapshot() {
  [[ -n "${RELEASE_SNAPSHOT_REFERENCE:-}" ]] \
    || fail "Falta RELEASE_SNAPSHOT_REFERENCE."
  [[ "${RELEASE_SNAPSHOT_CONFIRMED:-}" == "SNAPSHOT_PREVIO_VERIFICADO" ]] \
    || fail "Falta confirmar el snapshot previo."
  printf '%s' "$RELEASE_SNAPSHOT_REFERENCE" | sha256sum | awk '{print $1}'
}

require_maintenance() {
  [[ "$(systemctl is-active "$SERVICE_UNIT" 2>/dev/null || true)" != "active" ]] \
    || fail "El servicio sigue activo; mantenga la plataforma en mantenimiento."
}

marker_path() {
  printf '%s/gate-%s-%s.txt\n' "$OPS_DIR" "$HEAD_COMMIT" "$1"
}

marker_has() {
  local marker="$1" value="$2"
  [[ -f "$marker" ]] && grep -Fqx "$value" "$marker"
}

require_install_marker() {
  local marker backup_sha snapshot_sha
  marker="$(marker_path install)"
  backup_sha="$(validate_backup)"
  snapshot_sha="$(validate_snapshot)"
  marker_has "$marker" "release_commit=$HEAD_COMMIT" \
    || fail "Falta una instalación posterior a los respaldos para este SHA."
  marker_has "$marker" "backup_sha256=$backup_sha" \
    || fail "El dump cambió después de instalar dependencias."
  marker_has "$marker" "snapshot_reference_sha256=$snapshot_sha" \
    || fail "La referencia de snapshot cambió después de instalar dependencias."
}

require_preflight_route() {
  local route="$1" marker backup_sha snapshot_sha
  marker="$(marker_path preflight)"
  backup_sha="$(validate_backup)"
  snapshot_sha="$(validate_snapshot)"
  marker_has "$marker" "release_commit=$HEAD_COMMIT" \
    || fail "Falta preflight válido para este SHA."
  marker_has "$marker" "initial_route=$route" \
    || fail "El preflight no corresponde a ${route}."
  marker_has "$marker" "backup_sha256=$backup_sha" \
    || fail "El dump cambió después del preflight."
  marker_has "$marker" "snapshot_reference_sha256=$snapshot_sha" \
    || fail "La referencia de snapshot cambió después del preflight."
}

write_success_marker() {
  local label="$1" route="$2" marker
  marker="$(marker_path "$label")"
  printf 'release_tag=%s\nrelease_commit=%s\nroute=%s\ncompleted_at=%s\n' \
    "$EXPECTED_RELEASE_TAG" "$HEAD_COMMIT" "$route" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$marker"
}

require_success_marker() {
  local label="$1" marker
  marker="$(marker_path "$label")"
  marker_has "$marker" "release_commit=$HEAD_COMMIT" \
    || fail "Falta el marcador ${label} para este release."
}

run_timed_migration() {
  local label="$1" app="$2" target="$3" log
  log="$OPS_DIR/migrate-${label}.txt"
  if ! { /usr/bin/time -p "${DJANGO[@]}" migrate "$app" "$target" --noinput; } \
    2>&1 | tee "$log"; then
    echo "MIGRACIÓN FALLIDA. Mantenga mantenimiento; no restaure ni continúe automáticamente." >&2
    echo "Ejecute: scripts/release_asistencias_0005.sh diagnose-0005" >&2
    return 1
  fi
}

write_aggregate_report() {
  local stamp report
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  report="$OPS_DIR/relaciones-${stamp}-sanitizado.json"
  "${DJANGO[@]}" reportar_relaciones_historicas \
    --fecha-corte "${RELEASE_REPORT_DATE:-$(date +%F)}" \
    --dias-vigencia-alumno 90 \
    --formato=json \
    --fallar-si-inseguro > "$report"
  printf '%s\n' "$report"
}

report_review_count() {
  local report="$1"
  "$VENV_DIR/bin/python" -c \
    'import json, sys; data=json.load(open(sys.argv[1], encoding="utf-8")); print(sum(data[key]["requieren_revision_manual"] for key in ("asignaciones_profesor_disciplina", "matriculas_alumno_disciplina")))' \
    "$report"
}

validate_admin_actor() {
  local actor_id="$1"
  [[ "$actor_id" =~ ^[1-9][0-9]*$ ]] \
    || fail "RELEASE_ACTIVATION_USER_ID debe ser un User.id positivo."
  RELEASE_ACTIVATION_USER_ID="$actor_id" "${DJANGO[@]}" shell -c '
import os
from django.contrib.auth import get_user_model
from asistencias.models import AlumnoDisciplina, AsignacionProfesorDisciplina
from personas.permissions import (
    ACCION_ADMINISTRAR_PERSONAS,
    ACCION_ADMINISTRAR_SESIONES,
    usuario_tiene_permiso,
)

actor_id = int(os.environ["RELEASE_ACTIVATION_USER_ID"])
actor = get_user_model().objects.filter(pk=actor_id, is_active=True).first()
if actor is None:
    raise SystemExit("Actor administrativo inexistente o inactivo.")
organizaciones_profesor = set(
    AsignacionProfesorDisciplina.objects.filter(origen="historica", activa=False)
    .values_list("disciplina__organizacion_id", flat=True)
)
organizaciones_alumno = set(
    AlumnoDisciplina.objects.filter(origen="historica", activa=False)
    .values_list("disciplina__organizacion_id", flat=True)
)
for organizacion_id in organizaciones_profesor:
    if not usuario_tiene_permiso(
        actor,
        ACCION_ADMINISTRAR_SESIONES,
        organizacion=organizacion_id,
        permitir_staff_global=False,
    ):
        raise SystemExit("El actor no puede administrar sesiones en todo el alcance pendiente.")
for organizacion_id in organizaciones_alumno:
    if not usuario_tiene_permiso(
        actor,
        ACCION_ADMINISTRAR_PERSONAS,
        organizacion=organizacion_id,
        permitir_staff_global=False,
    ):
        raise SystemExit("El actor no puede administrar personas en todo el alcance pendiente.")
print(
    f"actor_user_id={actor.pk} organizaciones_profesor={len(organizaciones_profesor)} "
    f"organizaciones_alumno={len(organizaciones_alumno)} permisos=ok"
)
'
}

require_review_gate() {
  local report_marker activation_marker
  report_marker="$(marker_path report)"
  activation_marker="$(marker_path activations)"
  require_success_marker report
  if marker_has "$report_marker" "review_required=no"; then
    echo "Revisión: cero relaciones pendientes; sin activaciones requeridas."
    return 0
  fi
  marker_has "$report_marker" "review_required=yes" \
    || fail "El reporte no contiene una decisión de revisión válida."
  marker_has "$activation_marker" "release_commit=$HEAD_COMMIT" \
    || fail "Existen relaciones pendientes y falta confirmación administrativa."
  grep -Eq '^actor_user_id=[1-9][0-9]*$' "$activation_marker" \
    || fail "La confirmación administrativa no contiene un User.id verificable."
}

case "$ACTION" in
  install)
    require_maintenance
    backup_sha="$(validate_backup)"
    snapshot_sha="$(validate_snapshot)"
    "$VENV_DIR/bin/python" -m pip install --requirement requirements.txt
    "${DJANGO[@]}" check --deploy
    printf 'release_commit=%s\nbackup_sha256=%s\nsnapshot_reference_sha256=%s\ninstalled_at=%s\n' \
      "$HEAD_COMMIT" "$backup_sha" "$snapshot_sha" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$(marker_path install)"
    ;;
  preflight)
    state="$(current_state)"
    case "$state" in
      ROUTE_A_READY|ROUTE_B_READY_0004) ;;
      *) fail "Preflight inicial rechazado: ${state}. Use diagnose-0005 si es una reanudación." ;;
    esac
    require_maintenance
    require_install_marker
    backup_sha="$(validate_backup)"
    snapshot_sha="$(validate_snapshot)"
    validate_schema_before_0005 "$state"
    evidence="$OPS_DIR/preflight-${HEAD_COMMIT}.txt"
    {
      printf 'release_tag=%s\nrelease_commit=%s\nrelease_parent=%s\n' \
        "$EXPECTED_RELEASE_TAG" "$HEAD_COMMIT" "$HEAD_PARENT"
      printf 'worktree=clean\ninitial_route=%s\n' "$state"
      printf 'migration_file_0005=%s\n' \
        "$(sha256sum asistencias/migrations/0005_reparar_schema_0004_aplicada_precommit.py | awk '{print $1}')"
      "${DJANGO[@]}" showmigrations asistencias finanzas --list
      schema_report
      printf 'service=%s state=maintenance_inactive\n' "$SERVICE_UNIT"
      df -Pk "$APP_DIR" "$(dirname "$BACKUP_FILE")"
      findmnt -T "$BACKUP_FILE" --output SOURCE,TARGET,FSTYPE
      stat --format='backup_size=%s backup_mtime=%y' "$BACKUP_FILE"
      printf 'backup_sha256=%s\n' "$backup_sha"
      printf 'snapshot_reference_sha256=%s\n' "$snapshot_sha"
      printf 'preflight_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } | tee "$evidence"
    cp "$evidence" "$(marker_path preflight)"
    ;;
  route-a-migrate-0005)
    require_preflight_route ROUTE_A_READY
    require_maintenance
    require_state ROUTE_A_READY
    [[ "${RELEASE_CONFIRM_0005:-}" == "APLICAR_ASISTENCIAS_0005" ]] \
      || fail "Falta RELEASE_CONFIRM_0005=APLICAR_ASISTENCIAS_0005."
    validate_schema_before_0005 ROUTE_A_READY
    run_timed_migration asistencias-0005 asistencias 0005
    require_state COMPLETE
    validate_schema_after_0005
    write_success_marker 0005 ROUTE_A_READY
    ;;
  route-b-migrate-0004)
    require_preflight_route ROUTE_B_READY_0004
    require_maintenance
    require_state ROUTE_B_READY_0004
    [[ "${RELEASE_CONFIRM_0004:-}" == "APLICAR_ASISTENCIAS_0004" ]] \
      || fail "Falta RELEASE_CONFIRM_0004=APLICAR_ASISTENCIAS_0004."
    run_timed_migration asistencias-0004 asistencias 0004
    require_state ROUTE_B_READY_0005
    validate_schema_before_0005 ROUTE_B_READY_0005
    write_success_marker 0004 ROUTE_B_READY_0004
    ;;
  route-b-migrate-0005)
    require_preflight_route ROUTE_B_READY_0004
    require_success_marker 0004
    require_maintenance
    require_state ROUTE_B_READY_0005
    [[ "${RELEASE_CONFIRM_0005:-}" == "APLICAR_ASISTENCIAS_0005" ]] \
      || fail "Falta RELEASE_CONFIRM_0005=APLICAR_ASISTENCIAS_0005."
    validate_schema_before_0005 ROUTE_B_READY_0005
    run_timed_migration asistencias-0005 asistencias 0005
    require_state ROUTE_B_REVIEW
    validate_schema_after_0005
    write_success_marker 0005 ROUTE_B_READY_0004
    ;;
  report)
    require_success_marker 0005
    require_maintenance
    state="$(current_state)"
    [[ "$state" == "COMPLETE" || "$state" == "ROUTE_B_REVIEW" ]] \
      || fail "El reporte no corresponde al estado ${state}."
    report_path="$(write_aggregate_report)"
    review_count="$(report_review_count "$report_path")"
    review_mode="$(review_mode_from_count "$review_count")"
    [[ "$review_mode" != "INVALID" ]] || fail "El reporte no contiene un conteo de revisión válido."
    if [[ "$review_mode" == "REQUIRED" ]]; then
      review_required=yes
      echo "Reporte: ${review_count} relaciones requieren revisión administrativa."
    else
      review_required=no
      echo "Reporte: cero relaciones pendientes; sin activaciones requeridas."
    fi
    printf 'release_commit=%s\nreport_path=%s\nreview_count=%s\nreview_required=%s\nreported_at=%s\n' \
      "$HEAD_COMMIT" "$report_path" "$review_count" "$review_required" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$(marker_path report)"
    echo "Reporte agregado generado. Revíselo antes de cualquier activación."
    ;;
  confirm-activations)
    require_success_marker 0005
    require_success_marker report
    require_maintenance
    report_marker="$(marker_path report)"
    if marker_has "$report_marker" "review_required=no"; then
      echo "Cero relaciones pendientes: confirm-activations no requiere actor ni confirmación."
      printf 'release_commit=%s\noutcome=no_activations_required\nconfirmed_at=%s\n' \
        "$HEAD_COMMIT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        > "$(marker_path activations)"
      exit 0
    fi
    marker_has "$report_marker" "review_required=yes" \
      || fail "El reporte no contiene una decisión de revisión válida."
    actor_id="${RELEASE_ACTIVATION_USER_ID:-}"
    validate_admin_actor "$actor_id" | tee "$OPS_DIR/actor-validation-${HEAD_COMMIT}.txt"
    [[ "${RELEASE_CONFIRM_ACTIVACIONES:-}" == "RELACIONES_VIGENTES_REVISADAS" ]] \
      || fail "Falta la confirmación literal de revisión administrativa."
    write_aggregate_report >/dev/null
    printf 'release_commit=%s\nactor_user_id=%s\noutcome=relations_reviewed\nconfirmed_at=%s\n' \
      "$HEAD_COMMIT" "$actor_id" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$(marker_path activations)"
    ;;
  route-b-migrate-finanzas)
    require_preflight_route ROUTE_B_READY_0004
    require_success_marker 0005
    require_review_gate
    require_maintenance
    require_state ROUTE_B_REVIEW
    [[ "${RELEASE_CONFIRM_FINANZAS:-}" == "APLICAR_FINANZAS_0012" ]] \
      || fail "Falta RELEASE_CONFIRM_FINANZAS=APLICAR_FINANZAS_0012."
    run_timed_migration finanzas-0012 finanzas 0012
    require_state COMPLETE
    write_success_marker finanzas-0012 ROUTE_B_READY_0004
    ;;
  diagnose-0005)
    require_maintenance
    {
      printf 'release_tag=%s\nrelease_commit=%s\nstate=%s\n' \
        "$EXPECTED_RELEASE_TAG" "$HEAD_COMMIT" "$(current_state)"
      "${DJANGO[@]}" showmigrations asistencias finanzas --list
      schema_report
      printf 'diagnosed_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } | tee "$OPS_DIR/diagnose-0005-$(date -u +%Y%m%dT%H%M%SZ).txt"
    ;;
  finalize)
    require_success_marker 0005
    require_review_gate
    require_maintenance
    require_state COMPLETE
    validate_schema_after_0005
    "${DJANGO[@]}" migrate --check
    "${DJANGO[@]}" check --deploy
    "${DJANGO[@]}" showmigrations asistencias finanzas --plan \
      | tee "$OPS_DIR/showmigrations-final-${HEAD_COMMIT}.txt"
    echo "Validación final completa; el arranque y smoke siguen siendo pasos manuales del runbook."
    ;;
  *)
    usage
    fail "Acción desconocida: $ACTION"
    ;;
esac
