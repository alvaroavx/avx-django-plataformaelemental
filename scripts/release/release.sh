#!/usr/bin/env bash
# Releases y recuperación estilo Capistrano para una app Django.
#
# Este archivo es idéntico en avx-django-plataformaelemental y avx-django-cuadratura.
# Si se cambia en uno, copiarlo al otro (ver docs/operacion/RELEASES.md).
#
# Estructura en el servidor (DEPLOY_ROOT):
#   repo.git/                        espejo del repositorio (git clone --mirror)
#   releases/<UTC>-<sha12>/          código del commit + .venv + estáticos + REVISION
#   current -> releases/<id>         versión activa (la usa systemd y Nginx)
#   shared/                          lo que sobrevive entre releases (env, media)
#   releases.log                     historial de deploys, rollbacks y restauraciones
# Respaldos de base: BACKUP_DIR/<app>-<id>.dump (+ .sha256), fuera de DEPLOY_ROOT.
#
# Uso:
#   release.sh -c <config> deploy <sha40>
#   release.sh -c <config> rollback [<release_id>]
#   release.sh -c <config> restore-db <archivo.dump> --confirm <POSTGRES_DB>
#   release.sh -c <config> list
#   release.sh -c <config> cleanup

set -euo pipefail
umask 027

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

CONFIG=""
if [[ "${1:-}" == "-c" ]]; then
  CONFIG="${2:-}"
  shift 2 || true
fi
[[ -n "$CONFIG" && -f "$CONFIG" ]] || die "Indica la configuración con -c <archivo> (ver deploy/release.conf.example)."
# shellcheck disable=SC1090
source "$CONFIG"

: "${APP_NAME:?APP_NAME es obligatorio}"
: "${DEPLOY_ROOT:?DEPLOY_ROOT es obligatorio}"
: "${ENV_FILE:?ENV_FILE es obligatorio}"
: "${BACKUP_DIR:?BACKUP_DIR es obligatorio}"
: "${DJANGO_SETTINGS_MODULE:?DJANGO_SETTINGS_MODULE es obligatorio}"
SERVICE="${SERVICE:-$APP_NAME}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
KEEP_BACKUPS="${KEEP_BACKUPS:-20}"
SHARED_LINKS="${SHARED_LINKS:-}"
HEALTH_URL="${HEALTH_URL:-}"
HEALTH_HOST="${HEALTH_HOST:-}"
HEALTH_RETRIES="${HEALTH_RETRIES:-15}"
HOOKS_FILE="${HOOKS_FILE:-deploy/hooks.sh}"
# Solo para pruebas locales: script que recibe start|stop|restart en vez de systemctl.
SERVICE_CONTROL="${SERVICE_CONTROL:-}"

RELEASES_DIR="$DEPLOY_ROOT/releases"
SHARED_DIR="$DEPLOY_ROOT/shared"
REPO_DIR="$DEPLOY_ROOT/repo.git"
CURRENT_LINK="$DEPLOY_ROOT/current"
HISTORY="$DEPLOY_ROOT/releases.log"

[[ "$DEPLOY_ROOT" == /* ]] || die "DEPLOY_ROOT debe ser una ruta absoluta."
[[ "$BACKUP_DIR" == /* ]] || die "BACKUP_DIR debe ser una ruta absoluta."
case "$BACKUP_DIR/" in "$DEPLOY_ROOT"/*) die "BACKUP_DIR no puede estar dentro de DEPLOY_ROOT.";; esac

# ---------------------------------------------------------------- utilidades

service_ctl() {
  local action="$1"
  # 9>&- : el servicio no debe heredar el descriptor del lock de releases.
  if [[ -n "$SERVICE_CONTROL" ]]; then
    "$SERVICE_CONTROL" "$action" 9>&-
  else
    systemctl "$action" "${SERVICE}.service" 9>&-
  fi
}

load_env() {
  [[ -f "$ENV_FILE" ]] || die "No existe ENV_FILE: $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  export DJANGO_SETTINGS_MODULE
  : "${POSTGRES_DB:?Falta POSTGRES_DB en ENV_FILE}"
  : "${POSTGRES_USER:?Falta POSTGRES_USER en ENV_FILE}"
  : "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD en ENV_FILE}"
  POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
  POSTGRES_PORT="${POSTGRES_PORT:-5432}"
}

current_release() {
  [[ -L "$CURRENT_LINK" ]] || return 0
  basename "$(readlink -f "$CURRENT_LINK")"
}

# Releases ordenadas de la más antigua a la más nueva (el id empieza con la fecha UTC).
list_release_ids() {
  [[ -d "$RELEASES_DIR" ]] || return 0
  find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
}

record() {
  # fecha | acción | release | commit | anterior | respaldo | migró | resultado
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$@" >> "$HISTORY"
}

switch_current() {
  local target="$1"
  [[ -d "$RELEASES_DIR/$target" ]] || die "No existe la release $target"
  ln -sfn "releases/$target" "$DEPLOY_ROOT/.current.tmp"
  mv -Tf "$DEPLOY_ROOT/.current.tmp" "$CURRENT_LINK"
  log "current -> releases/$target"
}

health_check() {
  [[ -n "$HEALTH_URL" ]] || { log "Sin HEALTH_URL: se omite el chequeo de salud."; return 0; }
  local i args=(-fsS -o /dev/null --max-time 5)
  [[ -n "$HEALTH_HOST" ]] && args+=(-H "Host: $HEALTH_HOST")
  for ((i = 1; i <= HEALTH_RETRIES; i++)); do
    if curl "${args[@]}" "$HEALTH_URL" 2>/dev/null; then
      log "Salud OK ($HEALTH_URL)"
      return 0
    fi
    sleep 2
  done
  return 1
}

manage() { "$RELEASE_PATH/.venv/bin/python" "$RELEASE_PATH/manage.py" "$@"; }

run_hook() {
  local name="$1"
  if declare -F "$name" >/dev/null; then
    log "Hook $name"
    "$name"
  fi
}

backup_database() {
  local label="$1" file
  mkdir -p "$BACKUP_DIR"
  [[ -w "$BACKUP_DIR" ]] || die "BACKUP_DIR no permite escritura: $BACKUP_DIR"
  file="$BACKUP_DIR/${APP_NAME}-${label}.dump"
  PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
    --username "$POSTGRES_USER" --format=custom --no-owner --no-acl --file "$file" "$POSTGRES_DB"
  pg_restore --list "$file" >/dev/null
  (cd "$BACKUP_DIR" && sha256sum "$(basename "$file")" > "$(basename "$file").sha256")
  chmod 600 "$file" "$file.sha256"
  echo "$file"
}

cleanup() {
  local current previous ids count remove id
  current="$(current_release)"
  previous="$(previous_release "$current")"
  mapfile -t ids < <(list_release_ids)
  count="${#ids[@]}"
  if (( count > KEEP_RELEASES )); then
    remove=$((count - KEEP_RELEASES))
    for id in "${ids[@]:0:remove}"; do
      [[ "$id" == "$current" || "$id" == "$previous" ]] && continue
      rm -rf "${RELEASES_DIR:?}/$id"
      log "Release antigua eliminada: $id"
    done
  fi
  if [[ -d "$BACKUP_DIR" ]]; then
    find "$BACKUP_DIR" -maxdepth 1 -name "${APP_NAME}-*.dump" -printf '%f\n' | sort -r \
      | tail -n +"$((KEEP_BACKUPS + 1))" | while read -r old; do
        rm -f "$BACKUP_DIR/$old" "$BACKUP_DIR/$old.sha256"
        log "Respaldo antiguo eliminado: $old"
      done
  fi
}

previous_release() {
  local current="$1" prev="" id
  while read -r id; do
    [[ "$id" == "$current" ]] && { echo "$prev"; return 0; }
    prev="$id"
  done < <(list_release_ids)
}

# ---------------------------------------------------------------- comandos

cmd_deploy() {
  local sha="${1:-}" release_id previous backup="" migrated="no"
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || die "deploy necesita el hash completo del commit (40 caracteres)."
  [[ -d "$REPO_DIR" ]] || die "Falta el espejo $REPO_DIR (ver bootstrap en docs/operacion/RELEASES.md)."

  log "Actualizando espejo del repositorio"
  git --git-dir="$REPO_DIR" remote update --prune >/dev/null
  git --git-dir="$REPO_DIR" cat-file -e "${sha}^{commit}" || die "El commit $sha no existe en el espejo."

  release_id="$(date -u +%Y%m%dT%H%M%SZ)-${sha:0:12}"
  RELEASE_PATH="$RELEASES_DIR/$release_id"
  previous="$(current_release)"
  mkdir -p "$RELEASES_DIR" "$SHARED_DIR"
  mkdir "$RELEASE_PATH"
  trap 'log "Deploy interrumpido; la release incompleta queda en $RELEASE_PATH y current no cambió."' ERR

  log "Exportando $sha a releases/$release_id"
  git --git-dir="$REPO_DIR" archive "$sha" | tar -x -C "$RELEASE_PATH"
  echo "$sha" > "$RELEASE_PATH/REVISION"

  local path
  for path in $SHARED_LINKS; do
    mkdir -p "$SHARED_DIR/$path"
    rm -rf "${RELEASE_PATH:?}/$path"
    mkdir -p "$(dirname "$RELEASE_PATH/$path")"
    ln -s "$SHARED_DIR/$path" "$RELEASE_PATH/$path"
  done

  log "Creando entorno virtual con $PYTHON_BIN"
  "$PYTHON_BIN" -m venv "$RELEASE_PATH/.venv"
  "$RELEASE_PATH/.venv/bin/python" -m pip install --quiet --disable-pip-version-check -r "$RELEASE_PATH/requirements.txt"

  load_env
  if [[ -f "$RELEASE_PATH/$HOOKS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$RELEASE_PATH/$HOOKS_FILE"
  fi
  run_hook pre_checks

  log "Chequeos de Django"
  manage check --deploy --fail-level ERROR
  manage makemigrations --check --dry-run >/dev/null
  manage collectstatic --noinput >/dev/null
  run_hook post_collectstatic

  if manage migrate --check >/dev/null 2>&1; then
    log "Sin migraciones pendientes; respaldo en caliente"
    backup="$(backup_database "$release_id")"
  else
    log "Migraciones pendientes:"
    manage migrate --plan
    run_hook pre_migrate
    log "Deteniendo $SERVICE para respaldar y migrar sin escrituras"
    service_ctl stop
    if ! backup="$(backup_database "$release_id")"; then
      record deploy "$release_id" "$sha" "${previous:--}" "-" "no" "fallo-respaldo"
      die "Falló el respaldo. El servicio quedó detenido y current sigue en ${previous:-ninguna}. Para volver: release.sh -c $CONFIG rollback ${previous}"
    fi
    if ! manage migrate --noinput; then
      record deploy "$release_id" "$sha" "${previous:--}" "$backup" "parcial" "fallo-migracion"
      die "Falló la migración. Servicio detenido, current sin cambios. Restaurar con: release.sh -c $CONFIG restore-db $backup --confirm $POSTGRES_DB y luego service start."
    fi
    migrated="si"
  fi
  log "Respaldo: $backup"

  switch_current "$release_id"
  service_ctl restart
  if ! health_check; then
    log "La salud falló; volviendo a ${previous:-ninguna}"
    if [[ -n "$previous" ]]; then
      switch_current "$previous"
      service_ctl restart
    fi
    record deploy "$release_id" "$sha" "${previous:--}" "$backup" "$migrated" "fallo-salud-rollback"
    if [[ "$migrated" == "si" ]]; then
      die "Código revertido, pero la base YA está migrada. Si la versión anterior falla, restaurar: release.sh -c $CONFIG restore-db $backup --confirm $POSTGRES_DB"
    fi
    die "Código revertido a ${previous:-ninguna}. La base no cambió."
  fi
  trap - ERR

  record deploy "$release_id" "$sha" "${previous:--}" "$backup" "$migrated" "ok"
  run_hook post_deploy
  cleanup
  log "Deploy OK: $release_id"
}

cmd_rollback() {
  local target="${1:-}" current
  current="$(current_release)"
  [[ -n "$current" ]] || die "No hay release activa."
  if [[ -z "$target" ]]; then
    target="$(previous_release "$current")"
    [[ -n "$target" ]] || die "No hay una release anterior a $current."
  fi
  [[ "$target" != "$current" ]] || die "$target ya es la release activa."
  [[ -x "$RELEASES_DIR/$target/.venv/bin/python" ]] || die "La release $target no está completa."

  switch_current "$target"
  service_ctl restart
  if health_check; then
    record rollback "$target" "$(cat "$RELEASES_DIR/$target/REVISION")" "$current" "-" "no" "ok"
    log "Rollback OK: $current -> $target"
    log "La base NO se tocó. Si $current aplicó migraciones que $target no entiende, restaurar el respaldo de ese deploy:"
    grep -P "\tdeploy\t$current\t" "$HISTORY" | cut -f6 || true
  else
    record rollback "$target" "-" "$current" "-" "no" "fallo-salud"
    die "Rollback hecho pero la salud falla. Revisar logs: journalctl -u $SERVICE -n 100"
  fi
}

cmd_restore_db() {
  local file="${1:-}" flag="${2:-}" confirm="${3:-}" safety
  [[ -f "$file" ]] || die "No existe el respaldo: $file"
  load_env
  [[ "$flag" == "--confirm" && "$confirm" == "$POSTGRES_DB" ]] \
    || die "Restaurar reemplaza la base completa. Repite con: --confirm $POSTGRES_DB"
  if [[ -f "$file.sha256" ]]; then
    (cd "$(dirname "$file")" && sha256sum --check --quiet "$(basename "$file").sha256") || die "El checksum no coincide."
  fi
  pg_restore --list "$file" >/dev/null

  log "Respaldo de seguridad del estado actual antes de restaurar"
  safety="$(backup_database "pre-restore-$(date -u +%Y%m%dT%H%M%SZ)")"
  log "Guardado en $safety"
  service_ctl stop
  # pg_restore --clean solo borra lo que trae el respaldo; una tabla creada después
  # sobreviviría. Se borra todo lo del usuario de la app y se restaura en UNA transacción:
  # si algo falla, la base queda como estaba.
  if ! { echo "DROP OWNED BY CURRENT_USER;"; pg_restore --no-owner --no-acl --file - "$file"; } \
    | PGPASSWORD="$POSTGRES_PASSWORD" psql --host "$POSTGRES_HOST" --port "$POSTGRES_PORT" \
      --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --single-transaction \
      --set ON_ERROR_STOP=1 --quiet --output /dev/null; then
    service_ctl start
    die "Falló la restauración; la transacción se revirtió y la base sigue como antes."
  fi
  service_ctl start
  if health_check; then
    record restore-db "$(current_release)" "-" "-" "$file" "-" "ok"
    log "Base restaurada desde $file"
  else
    record restore-db "$(current_release)" "-" "-" "$file" "-" "fallo-salud"
    die "Base restaurada pero la salud falla. El estado previo quedó en $safety"
  fi
}

cmd_list() {
  local current id
  current="$(current_release)"
  while read -r id; do
    if [[ "$id" == "$current" ]]; then echo "* $id  (activa)"; else echo "  $id"; fi
  done < <(list_release_ids)
  if [[ -f "$HISTORY" ]]; then
    echo
    echo "Últimos movimientos:"
    tail -n 10 "$HISTORY"
  fi
}

ACTION="${1:-}"
shift || true
mkdir -p "$DEPLOY_ROOT"
exec 9>"$DEPLOY_ROOT/.release.lock"
flock -n 9 || die "Hay otra operación de release en curso."

case "$ACTION" in
  deploy) cmd_deploy "$@" ;;
  rollback) cmd_rollback "$@" ;;
  restore-db) cmd_restore_db "$@" ;;
  list) cmd_list ;;
  cleanup) cleanup ;;
  *) die "Acción desconocida: '$ACTION'. Usa deploy, rollback, restore-db, list o cleanup." ;;
esac
