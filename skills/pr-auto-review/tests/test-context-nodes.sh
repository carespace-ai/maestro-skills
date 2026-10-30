#!/usr/bin/env bash
# Context Layer node selection: root first, nearest node per file, CLAUDE.md only as fallback.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"
printf '%s\n' AGENTS.md CLAUDE.md backend/AGENTS.md backend/CLAUDE.md \
  backend/app/services/AGENTS.md backend/app/services/billing.py backend/app/api/routes.py \
  frontend/CLAUDE.md frontend/src/App.tsx docs/readme.md > "$T/tree.txt"
printf '%s\n' backend/app/services/billing.py backend/app/api/routes.py frontend/src/App.tsx > "$T/files.txt"

GOT="$(python3 "$SCRIPTS/context-nodes.py" "$T/files.txt" "$T/tree.txt" | tr '\n' ' ')"
WANT="AGENTS.md backend/AGENTS.md backend/app/services/AGENTS.md frontend/CLAUDE.md "
# nearest nodes: backend (routes.py), backend/app/services (billing.py), frontend (App.tsx) — 1 file each, sorted by path
[ "$GOT" = "$WANT" ] || fail "order: want [$WANT] got [$GOT]"; pass "priority order + CLAUDE.md fallback"

printf '%s\n' src/index.ts > "$T/tree2.txt"
GOT="$(python3 "$SCRIPTS/context-nodes.py" "$T/files.txt" "$T/tree2.txt")"
[ -z "$GOT" ] || fail "repo without Context Layer should select nothing, got: $GOT"; pass "no context layer → empty"
echo "ALL PASS"
