#!/usr/bin/env bash
# Review payload: marker always present, pinned commit, shadow downgrade, inline comments.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"; echo "Adds the billing export endpoint." > "$T/body.md"
echo '[{"path":"src/a.ts","line":"12","body":"crash when user is null"}]' > "$T/c.json"
SHA=abc123
field() { python3 -c 'import json,sys; v=json.load(sys.stdin); [v:=v[k] if not k.isdigit() else v[int(k)] for k in sys.argv[1].split(".")]; print(v)' "$1"; }

P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$T/body.md")"
[ "$(echo "$P" | field event)" = APPROVE ] || fail "event"; pass "approve event"
[ "$(echo "$P" | field commit_id)" = $SHA ] || fail "commit_id"; pass "pinned to head sha"
echo "$P" | field body | grep -q "<!-- maestro-pr-review sha=$SHA verdict=APPROVE -->" || fail "marker"; pass "marker"

P="$(PRR_DRY_RUN=1 SHADOW=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA REQUEST_CHANGES "$T/body.md" "$T/c.json")"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "shadow should downgrade to COMMENT"; pass "shadow downgrade"
echo "$P" | field body | grep -q "verdict=REQUEST_CHANGES" || fail "shadow keeps real verdict in marker"; pass "shadow marker"
[ "$(echo "$P" | field comments.0.line)" = 12 ] || fail "inline line int"; pass "inline comment"
[ "$(echo "$P" | field comments.0.side)" = RIGHT ] || fail "inline side"; pass "inline side RIGHT"

OUT="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA COMMENT "$T/body.md")"; RC=$?
[ $RC -eq 2 ] || fail "invalid verdict should exit 2 (got $RC: $OUT)"; pass "rejects non-review verdict"
echo "ALL PASS"
