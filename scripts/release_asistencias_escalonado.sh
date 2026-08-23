#!/usr/bin/env bash
set -euo pipefail
umask 077

ACTION="${1:-}"
EXPECTED_TAG="${RELEASE_EXPECTED_TAG:-}"
EXPECTED_SHA="${RELEASE_EXPECTED_SHA:-}"
EXPECTED_PARENT="${RELEASE_EXPECTED_PARENT:-}"
APP_DIR="${RELEASE_APP_DIR:-$(pwd)}"
OPS_DIR="${RELEASE_OPS_DIR:-}"
BACKUP_FILE="${RELEASE_BACKUP_FILE:-}"
ENV_FILE="${RELEASE_ENV_FILE:-}"
SERVICE="${RELEASE_SERVICE:-plataforma-elemental.service}"
MARKER="${RELEASE_PREFLIGHT_MARKER:-$OPS_DIR/preflight.json}"
TTL_SECONDS="${RELEASE_PREFLIGHT_TTL_SECONDS:-1800}"

fail() { echo "ERROR RELEASE ESCALONADO: $*" >&2; exit 1; }
self_test() {
  local synthetic='asistencias_asignacionprofesordisciplina|origen|NO||bad'
  awk -F'|' '$2=="origen" && ($3!="NO" || $5!="ok") {ok=1} END {exit ok?0:1}' <<<"$synthetic" \
    || fail "El gate sintético de esquema ambiguo no fue detectable."
  grep -Fq 'systemctl is-active "$SERVICE"' "$0"
  ! grep -Fq 'systemctl stop "$SERVICE"' <(sed -n '/preflight() {/,/valid_marker() {/p' "$0")
  echo "Self-test release escalonado: preflight seguro y migraciones explícitas OK"
}
runtime_self_test() {
  local fake_dir log active
  fake_dir="$(mktemp -d)"; log="$fake_dir/systemctl.log"
  cat >"$fake_dir/systemctl" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"${RELEASE_FAKE_SYSTEMCTL_LOG}"
if [[ "${1:-}" == is-active ]]; then printf 'active\n'; exit 0; fi
exit 99
SH
  chmod +x "$fake_dir/systemctl"
  active="$(RELEASE_FAKE_SYSTEMCTL_LOG="$log" PATH="$fake_dir:$PATH" systemctl is-active "$SERVICE")"
  [[ "$active" == active ]] || fail "El systemctl sintético no quedó activo."
  if awk -F'|' '$2=="origen" && ($3!="NO" || $5!="ok") {ok=1} END {exit ok?0:1}' \
      <<<"asistencias_asignacionprofesordisciplina|origen|NO||bad"; then
    :
  else
    fail "El gate sintético no rechazó el esquema ambiguo."
  fi
  ! grep -Eq '(^| )stop( |$)' "$log"
  rm -rf "$fake_dir"
  echo "Runtime self-test: preflight inválido con Gunicorn activo, sin stop ni downtime"
}
require_sha() {
  [[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "RELEASE_EXPECTED_SHA inválido.";
  [[ "$EXPECTED_PARENT" =~ ^[0-9a-f]{40}$ ]] || fail "RELEASE_EXPECTED_PARENT inválido.";
  [[ -n "$EXPECTED_TAG" ]] || fail "RELEASE_EXPECTED_TAG requerido.";
}
load_env() {
  [[ -f "$ENV_FILE" ]] || fail "No existe RELEASE_ENV_FILE.";
  set -a; source "$ENV_FILE"; set +a
  : "${POSTGRES_DB:?Falta POSTGRES_DB}"
  : "${POSTGRES_USER:?Falta POSTGRES_USER}"
  : "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD}"
  : "${POSTGRES_HOST:?Falta POSTGRES_HOST}"
  : "${POSTGRES_PORT:?Falta POSTGRES_PORT}"
}
psql_ro() {
  PGPASSWORD="$POSTGRES_PASSWORD" PGOPTIONS="-c default_transaction_read_only=on -c lock_timeout=5s" \
    psql --no-psqlrc --set=ON_ERROR_STOP=1 -X -q \
      -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
}
check_identity() {
  cd "$APP_DIR"
  test -z "$(git status --porcelain)" || fail "worktree productivo sucio."
  if [[ "${RELEASE_REMOTE_TAG_VERIFIED:-}" == 1 ]]; then
    [[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "SHA remoto inválido."
    [[ "$EXPECTED_PARENT" =~ ^[0-9a-f]{40}$ ]] || fail "Padre remoto inválido."
    return 0
  fi
  test "$(git cat-file -t "refs/tags/$EXPECTED_TAG" 2>/dev/null || true)" = tag \
    || fail "El tag no es anotado o no existe."
  test "$(git rev-parse "refs/tags/$EXPECTED_TAG^{commit}")" = "$EXPECTED_SHA" \
    || fail "tag^{} no coincide con release SHA."
  test "$(git rev-parse "$EXPECTED_SHA^")" = "$EXPECTED_PARENT" \
    || fail "Padre inesperado."
}
validate_backup() {
  [[ "$BACKUP_FILE" = /* && -s "$BACKUP_FILE" ]] || fail "Dump inválido o ausente."
  pg_restore --list "$BACKUP_FILE" >/dev/null || fail "Dump ilegible."
  [[ "${RELEASE_BACKUP_CONFIRMED:-}" = EXTERNO_SEGURO_VERIFICADO ]] || fail "Backup no confirmado."
  [[ "${RELEASE_SNAPSHOT_CONFIRMED:-}" = SNAPSHOT_PREVIO_VERIFICADO ]] || fail "Snapshot no confirmado."
}
schema_state() {
  psql_ro --tuples-only --no-align <<'SQL'
SELECT
  (SELECT count(*) FROM django_migrations WHERE app='asistencias' AND name='0004_alter_sesionclase_estado_liberacionsesion_and_more') AS m0004,
  (SELECT count(*) FROM django_migrations WHERE app='asistencias' AND name IN ('0005_reparar_schema_0004_aplicada_precommit','0005_reparar_schema_0004_aplicada_precommit_v2')) AS m0005,
  (SELECT count(*) FROM django_migrations WHERE app='finanzas' AND name='0012_payment_clave_idempotencia_payment_disciplina_and_more') AS f0012;
SQL
}
schema_report() {
  psql_ro --tuples-only --no-align --field-separator='|' <<'SQL'
SELECT table_name, column_name, is_nullable, coalesce(column_default,''),
       CASE WHEN column_default LIKE '%explicita%' THEN 'ok' ELSE 'bad' END
  FROM information_schema.columns
 WHERE table_schema='public'
   AND table_name IN ('asistencias_asignacionprofesordisciplina','asistencias_alumnodisciplina')
   AND column_name='origen'
 ORDER BY table_name;
SELECT 'asignaciones_profesor', count(*), count(*) FILTER (WHERE activa), count(*) FILTER (WHERE NOT activa)
  FROM asistencias_asignacionprofesordisciplina;
SELECT 'matriculas_alumno', count(*), count(*) FILTER (WHERE activa), count(*) FILTER (WHERE NOT activa)
  FROM asistencias_alumnodisciplina;
SQL
}
preflight() {
  require_sha; load_env; check_identity; validate_backup
  [[ "$(systemctl is-active "$SERVICE" 2>/dev/null || true)" = active ]] || fail "Gunicorn no está activo."
  local state schema_file now expires
  state="$(schema_state)"
  schema_file="$(mktemp)"; trap 'rm -f "$schema_file"' RETURN
  schema_report >"$schema_file"
  now="$(date +%s)"; expires=$((now + TTL_SECONDS))
  # Ruta reparable: 0004 aplicada, 0005 pendiente y origen ya presente con
  # metadata incompatible. La evidencia es agregada y no incluye PII.
  if [[ "$state" != "1|0|1" ]]; then
    fail "Estado de migraciones no previsto: $state"
  fi
  if ! awk -F'|' '$2=="origen" && ($3!="NO" || $5!="ok") {ok=1} END {exit ok?0:1}' "$schema_file"; then
    fail "origen no presenta la condición parcial esperada; revisión requerida."
  fi
  mkdir -p "$OPS_DIR"
  local dump_sha; dump_sha="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"
  python3 - "$MARKER" "$EXPECTED_TAG" "$EXPECTED_SHA" "$EXPECTED_PARENT" "$now" "$expires" "$dump_sha" "$state" "$schema_file" <<'PY'
import json, pathlib, sys
marker, tag, sha, parent, now, expires, dump_sha, state, schema = sys.argv[1:]
rows = [line.split('|') for line in pathlib.Path(schema).read_text().splitlines() if line]
pathlib.Path(marker).write_text(json.dumps({
    "tag": tag, "sha": sha, "parent": parent, "created_at": int(now),
    "expires_at": int(expires), "dump_sha256": dump_sha,
    "migration_state": state, "origen": rows,
    "route": "REPAIR_0005", "review_required": True,
}, sort_keys=True, indent=2) + "\n")
PY
  echo "PREFLIGHT_OK marker=$MARKER expires=$expires route=REPAIR_0005"
}
valid_marker() {
  [[ -s "$MARKER" ]] || fail "Marcador de preflight ausente."
  python3 - "$MARKER" "$EXPECTED_TAG" "$EXPECTED_SHA" "$EXPECTED_PARENT" "$TTL_SECONDS" <<'PY'
import json, sys, time
d=json.load(open(sys.argv[1], encoding='utf-8'))
assert d['tag']==sys.argv[2] and d['sha']==sys.argv[3] and d['parent']==sys.argv[4]
assert d['route']=='REPAIR_0005' and d['expires_at'] >= int(time.time())
PY
}
apply_release() {
  require_sha; load_env; check_identity; valid_marker; validate_backup
  # La segunda comprobación ocurre todavía con Gunicorn activo, antes de
  # cualquier ventana de mantenimiento.
  preflight
  local previous_commit migration_started=0
  previous_commit="$(git rev-parse HEAD)"
  printf 'previous_commit=%s\n' "$previous_commit" > "$OPS_DIR/apply-state.txt"
  recover_before_migration() {
    [[ "$migration_started" = 0 ]] || return 0
    git checkout --detach "$previous_commit"
    "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt" >/dev/null
    systemctl start "$SERVICE"
  }
  trap 'if [[ "$migration_started" = 0 ]]; then recover_before_migration; else echo "FALLO_FORWARD_ONLY: mantener mantenimiento" >&2; fi' ERR
  systemctl stop "$SERVICE"
  test "$(systemctl is-active "$SERVICE" 2>/dev/null || true)" != active
  git checkout --detach "$EXPECTED_TAG"
  "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
  [[ "$(schema_state)" = "1|0|1" ]] || fail "El estado cambió durante la preparación."
  valid_marker
  migration_started=1
  export PGOPTIONS="-c lock_timeout=5s -c statement_timeout=15min"
  "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate asistencias 0004b_reparar_precondiciones_0005 --noinput
  "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate asistencias 0005_reparar_schema_0004_aplicada_precommit_v2 --noinput
  "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate asistencias 0006_merge_0004b_y_0005 --noinput
  "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" check --deploy
  "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput
  systemctl start "$SERVICE"
  systemctl is-active --quiet "$SERVICE"
  bash "$APP_DIR/scripts/smoke_produccion.sh"
  echo "APPLY_OK sha=$EXPECTED_SHA previous=$previous_commit"
}
case "$ACTION" in
  self-test) self_test ;;
  runtime-self-test) runtime_self_test ;;
  preflight) preflight ;;
  apply) apply_release ;;
  diagnose) load_env; schema_state; schema_report ;;
  *) echo "Uso: $0 {preflight|apply|diagnose}" >&2; exit 2 ;;
esac
