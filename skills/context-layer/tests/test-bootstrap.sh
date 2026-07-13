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

# Case D (regression): a LARGE supported-language repo must be `ready`, not `fallback`.
# Guards the pipefail/SIGPIPE HAS_SRC bug where `find | head -1` under `set -o pipefail`
# wrongly reports "no supported source" on big repos (find dies with SIGPIPE after head
# closes the pipe). Uses a stub code-graph (no real indexing) so it runs even without
# code-graph installed.
STUB="$(mktemp -d)/code-graph-stub"
cat > "$STUB" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  health-check) echo '{"healthy":true,"nodes":600}' ;;
  *) : ;;
esac
SH
chmod +x "$STUB"
BIG="$(mktemp -d)/repo"; make_big_fixture "$BIG"; cd "$BIG"
OUT="$(CG_BIN="$STUB" bash "$BOOT")"
echo "$OUT" | grep -q '^CODEGRAPH=ready$' || fail "large supported-lang repo must be ready, got: $OUT"
pass "large-repo-ready (SIGPIPE regression)"

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
