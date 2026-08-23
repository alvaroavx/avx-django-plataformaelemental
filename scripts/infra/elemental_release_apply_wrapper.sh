#!/usr/bin/env bash
set -euo pipefail
readonly EXPECTED='^apply --tag release/[A-Za-z0-9._-]+ --sha [0-9a-f]{40} --parent [0-9a-f]{40}$'
readonly LAUNCHER=/usr/local/sbin/elemental-release-apply
[[ "${SSH_ORIGINAL_COMMAND:-}" =~ $EXPECTED ]] || exit 126
set -- ${SSH_ORIGINAL_COMMAND}
exec sudo -n "$LAUNCHER" "$3" "$5" "$7" </dev/null
