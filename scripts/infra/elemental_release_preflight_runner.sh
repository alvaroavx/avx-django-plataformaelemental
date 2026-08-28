#!/usr/bin/env bash
set -euo pipefail
umask 077
tag="$1"; sha="$2"; parent="$3"
app_dir=/srv/elementos
service=plataforma-elemental.service
state_dir=/var/lib/elemental-release
status_file="$state_dir/backup-status.json"
report="$state_dir/preflight-report.json"
marker="$state_dir/preflight.json"
pgpass=/etc/elemental-release-ro/pgpass

[[ "$tag" =~ ^release/[A-Za-z0-9._-]+$ ]]
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$parent" =~ ^[0-9a-f]{40}$ ]]
[[ "$(systemctl is-active "$service" 2>/dev/null || true)" = active ]]
[[ -r "$status_file" && -r "$pgpass" ]]
[[ -f "$app_dir/manage.py" ]]
rm -f "$state_dir/preflight.json"
if ! worktree_status="$(git -C "$app_dir" status --porcelain -- . ':(exclude).venv')"; then
  echo 'preflight: no se pudo comprobar el worktree' >&2
  exit 1
fi
[[ -z "$worktree_status" ]]

db_json="$(PGPASSFILE="$pgpass" psql --no-psqlrc --no-align --tuples-only \
  --host 127.0.0.1 --username elemental_release_ro \
  --dbname plataforma_elemental_prod --command 'SELECT elemental_release_preflight()')"
[[ "$db_json" == \{*\} ]]
schema_state="$(PGPASSFILE="$pgpass" psql --no-psqlrc --no-align --tuples-only --field-separator='|' \
  --host 127.0.0.1 --username elemental_release_ro --dbname plataforma_elemental_prod \
  --command "SELECT (SELECT count(*) FROM django_migrations WHERE app='asistencias' AND name='0004_alter_sesionclase_estado_liberacionsesion_and_more'), (SELECT count(*) FROM django_migrations WHERE app='asistencias' AND name IN ('0005_reparar_schema_0004_aplicada_precommit','0005_reparar_schema_0004_aplicada_precommit_v2')), (SELECT count(*) FROM django_migrations WHERE app='finanzas' AND name='0012_payment_clave_idempotencia_payment_disciplina_and_more'), (SELECT count(*) FROM django_migrations WHERE app='asistencias' AND name='0007_reconciliar_relaciones_activas')")"
[[ "$schema_state" = '1|0|1|0' ]] || { echo 'preflight: estado de migraciones no corresponde a la reparación esperada' >&2; exit 1; }
origin_schema="$(PGPASSFILE="$pgpass" psql --no-psqlrc --no-align --tuples-only --field-separator='|' \
  --host 127.0.0.1 --username elemental_release_ro --dbname plataforma_elemental_prod \
  --command "SELECT table_name, is_nullable, coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('asistencias_asignacionprofesordisciplina','asistencias_alumnodisciplina') AND column_name='origen' ORDER BY table_name")"
[[ "$(printf '%s\n' "$origin_schema" | sed '/^$/d' | wc -l)" = 2 ]] || { echo 'preflight: estructura de origen incompleta' >&2; exit 1; }
while IFS='|' read -r _ nullable _default; do
  [[ "$nullable" = NO ]] || { echo 'preflight: origen debe ser NOT NULL antes de reparar' >&2; exit 1; }
done <<<"$origin_schema"
active_json="$(PGPASSFILE="$pgpass" psql --no-psqlrc --no-align --tuples-only --field-separator='|' \
  --host 127.0.0.1 --username elemental_release_ro --dbname plataforma_elemental_prod \
  --command "SELECT 'profesor', count(*) FILTER (WHERE activa), count(*) FILTER (WHERE activa AND origen='historica') FROM asistencias_asignacionprofesordisciplina; SELECT 'alumno', count(*) FILTER (WHERE activa), count(*) FILTER (WHERE activa AND origen='historica') FROM asistencias_alumnodisciplina;")"
disk_json="$(df -Pk "$app_dir" | tail -1 | awk '{print "{\"filesystem\":\""$1"\",\"available_kb\":"$4"}"}')"
status_json="$(tr -d '\n' < "$status_file")"
python3 - "$report" "$marker" "$tag" "$sha" "$parent" "$db_json" "$disk_json" "$status_json" "$active_json" <<'PY'
import json
import hashlib
import pathlib
import sys
import time

report, marker, tag, sha, parent, db, disk, status, active = sys.argv[1:]
backup = json.loads(status)
active_rows = {}
for line in active.splitlines():
    if line:
        name, total, historical = line.split("|")
        active_rows[name] = {"active": int(total), "active_historical": int(historical)}
data = {
    "tag": tag,
    "sha": sha,
    "parent": parent,
    "created_at": int(time.time()),
    "expires_at": int(time.time()) + 1800,
    "service": "active",
    "database": json.loads(db),
    "disk": json.loads(disk),
    "backup_status": json.loads(status),
    "route": "REPAIR_0005",
    "review_required": False,
    "active_before": active_rows,
    "migration_state": "1|0|1|0",
}
data["dump_sha256"] = backup.get("dump_sha256", "")
if not data["dump_sha256"]:
    data["dump_sha256"] = backup.get("checksum", "")
data["snapshot_reference"] = backup.get("snapshot_reference", "")
data["snapshot_sha256"] = backup.get("snapshot_sha256", "")
pathlib.Path(report).write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
data["report_sha256"] = hashlib.sha256(pathlib.Path(report).read_bytes()).hexdigest()
pathlib.Path(marker).write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 640 "$report"
chmod 640 "$marker"
printf 'PREFLIGHT_OK tag=%s sha=%s marker=%s report=%s\n' "$tag" "$sha" "$marker" "$report"
