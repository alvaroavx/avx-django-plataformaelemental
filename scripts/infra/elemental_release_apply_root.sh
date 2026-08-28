#!/usr/bin/env bash
set -euo pipefail
umask 077
tag="$1"; sha="$2"; parent="$3"
[[ "$tag" =~ ^release/[A-Za-z0-9._-]+$ ]]
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$parent" =~ ^[0-9a-f]{40}$ ]]
cd /srv/elementos
if ! worktree_status="$(git status --porcelain -- . ':(exclude).venv')"; then
  echo 'apply: no se pudo comprobar el worktree' >&2
  exit 1
fi
test -z "$worktree_status"
git fetch --no-tags origin "refs/tags/$tag:refs/tags/$tag"
test "$(git cat-file -t "refs/tags/$tag")" = tag
test "$(git rev-parse "refs/tags/$tag^{commit}")" = "$sha"
test "$(git rev-parse "$sha^")" = "$parent"
release_script="$(mktemp /run/elemental-release-asistencias.XXXXXX)"
cleanup() { rm -f "$release_script"; }
trap cleanup EXIT
git show "$tag:scripts/release_asistencias_escalonado.sh" >"$release_script"
chmod 700 "$release_script"
bash -n "$release_script"
set -a
source /etc/elemental-release/apply.env
set +a
export RELEASE_EXPECTED_SHA="$sha" RELEASE_EXPECTED_TAG="$tag" RELEASE_EXPECTED_PARENT="$parent" RELEASE_APP_DIR=/srv/elementos
exec bash "$release_script" apply
