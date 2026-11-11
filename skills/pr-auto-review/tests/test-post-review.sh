#!/usr/bin/env bash
# Review payload: marker always present, pinned commit, shadow downgrade, inline comments.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"; echo "Adds the billing export endpoint." > "$T/body.md"
echo '[{"path":"src/a.ts","line":"12","body":"crash when user is null"}]' > "$T/c.json"
printf 'DIFF_STATUS=ok\nHUMAN_FILES=0\n' > "$T/status.env"   # fetch-context.sh staged the diff
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
printf 'DIFF_STATUS=partial\nHUMAN_FILES=0\n' > "$U/status.env"
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

# ── Human-only paths: the bot's findings go out, the approve does not
H="$(mktemp -d)"; cp "$T/body.md" "$H/body.md"
printf 'DIFF_STATUS=ok\nHUMAN_FILES=2\n' > "$H/status.env"
printf '.github/workflows/ci.yml\n.github/workflows/release.yml\n' > "$H/human-files.txt"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$H/body.md")"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "human path must not approve"; pass "human path → COMMENT"
echo "$P" | field body | grep -q 'Needs a human approve.*`.github/workflows/ci.yml`, `.github/workflows/release.yml`' || fail "human note lists files"; pass "human note lists the files"
echo "$P" | field body | grep -q "verdict=APPROVE held=human" || fail "human marker"; pass "human marker"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA REQUEST_CHANGES "$H/body.md")"
[ "$(echo "$P" | field event)" = REQUEST_CHANGES ] || fail "human path never softens a block"; pass "human path: block still blocks"
echo "DIFF_STATUS=ok" > "$H/status.env"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$H/body.md")"
[ "$(echo "$P" | field event)" = COMMENT ] || fail "unknown HUMAN_FILES must hold"; pass "HUMAN_FILES unknown → COMMENT (fails closed)"

# ── Head moved: nothing is posted, for any verdict
for v in APPROVE REQUEST_CHANGES; do
  OUT="$(PRR_HEAD_NOW=def456 PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA $v "$T/body.md")"
  echo "$OUT" | grep -q '^REVIEW_SKIPPED=head-moved$' && ! echo "$OUT" | grep -q commit_id || fail "moved head must post nothing ($v)"
done; pass "head moved during review → nothing posted"
OUT="$(PRR_HEAD_NOW=$SHA PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$T/body.md")"
[ "$(echo "$OUT" | field event)" = APPROVE ] || fail "same head posts"; pass "head unchanged → posts"
M="$(mktemp -d)"; cp "$T/body.md" "$M/body.md"; printf 'DIFF_STATUS=missing\nHEAD_MOVED=1\n' > "$M/status.env"
OUT="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA UNREVIEWED "$M/body.md")"
echo "$OUT" | grep -q '^REVIEW_SKIPPED=head-moved$' || fail "HEAD_MOVED in status.env must post nothing"; pass "head moved before staging → nothing posted"
# delta scope is recorded in the marker (and only when the staging says so)
D="$(mktemp -d)"; cp "$T/body.md" "$D/body.md"
printf 'DIFF_STATUS=ok\nHUMAN_FILES=0\nREVIEW_SCOPE=delta\nDELTA_BASE=9f3e0715933410597b45f2f1bb8d3ab99b1af659\n' > "$D/status.env"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$D/body.md")"
echo "$P" | field body | grep -q "verdict=APPROVE scope=delta base=9f3e07159334 -->" || fail "delta marker (got: $(echo "$P" | field body | tail -1))"; pass "delta review records its scope and base"
printf 'DIFF_STATUS=ok\nHUMAN_FILES=0\nREVIEW_SCOPE=delta\nDELTA_BASE=$(id)\n' > "$D/status.env"
P="$(PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 $SHA APPROVE "$D/body.md")"
echo "$P" | field body | grep -q "scope=delta" && fail "a malformed base must not reach the marker"; pass "malformed delta base ignored"
echo "ALL PASS"

# ── scripts patched mid-run: nothing is posted ──
G="$(mktemp -d)"; cp "$T/body.md" "$G/body.md"; cp "$T/status.env" "$G/status.env"
GOOD="$(python3 "$SCRIPTS/_fingerprint.py")"
OUT="$(SCRIPTS_SHA="$GOOD" PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 abc123 APPROVE "$G/body.md")"
echo "$OUT" | grep -q '^ERROR=' && fail "unchanged scripts must still post"; pass "matching SCRIPTS_SHA → posts"
OUT="$(SCRIPTS_SHA=deadbeef PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 abc123 APPROVE "$G/body.md")"; RC=$?
[ "$RC" = 3 ] && echo "$OUT" | grep -q '^ERROR=skill scripts were modified' || fail "changed scripts must post nothing"
echo "$OUT" | grep -q '"event"' && fail "changed scripts must not build a payload"; pass "SCRIPTS_SHA mismatch → nothing posted"
