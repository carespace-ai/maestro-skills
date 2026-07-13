#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
BOOT="$HERE/../scripts/codegraph-bootstrap.sh"

# Case A: binary absent → fallback (works even without code-graph installed)
A="$(mktemp -d)/repo"; make_fixture "$A"; cd "$A"
OUT="$(CG_BIN=definitely-not-a-real-bin bash "$BOOT")"
echo "$OUT" | grep -q '^CODEGRAPH=fallback$' || fail "absent binary should be fallback: $OUT"
pass "absent-binary-fallback"

command -v code-graph >/dev/null 2>&1 || { echo "SKIP rest: code-graph not installed"; echo "ALL PASS"; exit 0; }

# Case B: supported TS source → ready
B="$(mktemp -d)/repo"; make_fixture "$B"; cd "$B"
OUT="$(bash "$BOOT")"
echo "$OUT" | grep -q '^CODEGRAPH=ready$' || fail "TS fixture should be ready: $OUT"
pass "supported-ready"

# Case C: no supported source (only a .md) → fallback
C="$(mktemp -d)/repo"; mkdir -p "$C"; echo "# readme" > "$C/README.md"; cd "$C"
OUT="$(bash "$BOOT")"
echo "$OUT" | grep -q '^CODEGRAPH=fallback$' || fail "no-source repo should be fallback: $OUT"
pass "unsupported-fallback"
echo "ALL PASS"
