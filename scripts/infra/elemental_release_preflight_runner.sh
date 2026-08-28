#!/usr/bin/env bash
set -euo pipefail
umask 077
tag="$1"; sha="$2"; parent="$3"
app_dir=/srv/elementos
service=plataforma-elemental.service
state_dir=/var/lib/elemental-release
status_file="$state_dir/backup-status.json"
report="$state_dir/preflight-report.json"
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
disk_json="$(df -Pk "$app_dir" | tail -1 | awk '{print "{\"filesystem\":\""$1"\",\"available_kb\":"$4"}"}')"
status_json="$(tr -d '\n' < "$status_file")"
python3 - "$report" "$tag" "$sha" "$parent" "$db_json" "$disk_json" "$status_json" <<'PY'
import json
import pathlib
import sys
import time

report, tag, sha, parent, db, disk, status = sys.argv[1:]
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
    "review_required": True,
}
backup = data["backup_status"]
data["dump_sha256"] = backup.get("dump_sha256", "")
data["snapshot_reference"] = backup.get("snapshot_reference", "")
data["snapshot_sha256"] = backup.get("snapshot_sha256", "")
pathlib.Path(report).write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 640 "$report"
printf 'PREFLIGHT_REVIEW_REQUIRED tag=%s sha=%s report=%s\n' "$tag" "$sha" "$report" >&2
exit 1
