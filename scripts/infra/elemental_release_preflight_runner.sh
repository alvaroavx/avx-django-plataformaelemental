#!/usr/bin/env bash
set -euo pipefail
umask 077
tag="$1"; sha="$2"; parent="$3"
app_dir=/srv/elementos
service=plataforma-elemental.service
state_dir=/var/lib/elemental-release
status_file="$state_dir/backup-status.json"
marker="$state_dir/preflight.json"
pgpass=/etc/elemental-release-ro/pgpass

[[ "$tag" =~ ^release/[A-Za-z0-9._-]+$ ]]
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$parent" =~ ^[0-9a-f]{40}$ ]]
[[ "$(systemctl is-active "$service" 2>/dev/null || true)" = active ]]
[[ -r "$status_file" && -r "$pgpass" ]]
[[ -f "$app_dir/manage.py" ]]
[[ -z "$(git -C "$app_dir" status --porcelain)" ]]

db_json="$(PGPASSFILE="$pgpass" psql --no-psqlrc --no-align --tuples-only \
  --host 127.0.0.1 --username elemental_release_ro \
  --dbname plataforma_elemental_prod --command 'SELECT elemental_release_preflight()')"
[[ "$db_json" == \{*\} ]]
disk_json="$(df -Pk "$app_dir" | tail -1 | awk '{print "{\"filesystem\":\""$1"\",\"available_kb\":"$4"}"}')"
status_json="$(tr -d '\n' < "$status_file")"
python3 - "$marker" "$tag" "$sha" "$parent" "$db_json" "$disk_json" "$status_json" <<'PY'
import json
import pathlib
import sys
import time

marker, tag, sha, parent, db, disk, status = sys.argv[1:]
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
}
pathlib.Path(marker).write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 640 "$marker"
printf 'PREFLIGHT_OK tag=%s sha=%s marker=%s\n' "$tag" "$sha" "$marker"
