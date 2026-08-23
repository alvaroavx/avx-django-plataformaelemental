#!/usr/bin/env bash
set -euo pipefail
readonly EXPECTED='^preflight --tag release/[A-Za-z0-9._-]+ --sha [0-9a-f]{40} --parent [0-9a-f]{40}$'
readonly RUNNER=/usr/local/lib/elemental-release/preflight-runner
[[ "${SSH_ORIGINAL_COMMAND:-}" =~ $EXPECTED ]] || exit 126
set -- ${SSH_ORIGINAL_COMMAND}
exec "$RUNNER" "$3" "$5" "$7" </dev/null
