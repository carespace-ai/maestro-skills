#!/usr/bin/env bash
# Review payload: marker always present, pinned commit, shadow downgrade, inline comments.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"; echo "Adds the billing export endpoint." > "$T/body.md"
echo '[{"path":"src/a.ts","line":"12","body":"crash when user is null"}]' > "$T/c.json"
echo "DIFF_STATUS=ok" > "$T/status.env"   # fetch-context.sh staged the diff
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

# ── Approve gates: an APPROVE needs a diff that was read and a commit that is not red
U="$(mktemp -d)"; cp "$T/body.md" "$U/body.md"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$U/body.md")"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "no status.env must not approve"; pass "no staged status → COMMENT"
echo "DIFF_STATUS=missing" > "$U/status.env"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$U/body.md")"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "missing diff must not approve"; pass "unread diff → COMMENT"
echo "$P" | field body | grep -q "could not read this PR's diff" || fail "unread note"; pass "unread diff says so"
echo "$P" | field body | grep -q "verdict=APPROVE held=unread" || fail "unread marker"; pass "unread marker"
echo "DIFF_STATUS=partial" > "$U/status.env"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$U/body.md")"
[ "$(echo "$P" | field event)" = APPROVE ] || fail "partial diff may approve"; pass "partial diff → APPROVE"
echo "DIFF_STATUS=missing" > "$U/status.env"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA REQUEST_CHANGES "$U/body.md")"
[ "$(echo "$P" | field event)" = REQUEST_CHANGES ] || fail "gates only apply to APPROVE"; pass "block is never held"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA UNREVIEWED "$U/body.md")"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "UNREVIEWED → COMMENT"; pass "UNREVIEWED → COMMENT"

ci() { echo "$1" > "$T/ci.json"; PRR_CI_WAIT=0 PRR_CI_FILE="$T/ci.json" PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$T/body.md"; }
P="$(ci '{"check_runs":[{"name":"test","status":"completed","conclusion":"success"}]}')"
[ "$(echo "$P" | field event)" = APPROVE ] || fail "green CI approves"; pass "CI green → APPROVE"
echo "$P" | field body | grep -q "ci=success" || fail "ci in marker"; pass "CI state in marker"
P="$(ci '{"check_runs":[{"name":"test","status":"completed","conclusion":"failure"},{"name":"lint","status":"completed","conclusion":"success"}]}')"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "red CI must not approve"; pass "CI red → COMMENT"
echo "$P" | field body | grep -q "CI is failing on this commit:\*\* test" || fail "red CI names the check"; pass "CI red names the check"
P="$(ci '{"check_runs":[{"name":"build","status":"in_progress","conclusion":null}]}')"
[ "$(echo "$P" | field event)" = APPROVE ] || fail "pending CI approves with a note"; pass "CI pending → APPROVE"
echo "$P" | field body | grep -q "CI was still running" || fail "pending note"; pass "CI pending note"
P="$(PRR_CI_IGNORE='^preview' ci '{"check_runs":[{"name":"preview deploy","status":"completed","conclusion":"failure"},{"name":"test","status":"completed","conclusion":"success"}]}')"
[ "$(echo "$P" | field event)" = APPROVE ] || fail "ignored check must not hold"; pass "PRR_CI_IGNORE"
P="$(ci '{"check_runs":[{"name":"old","status":"completed","conclusion":"cancelled"}],"statuses":[{"context":"deploy","state":"error"}]}')"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "commit status error must hold"; pass "legacy status error → COMMENT"
echo "ALL PASS"
