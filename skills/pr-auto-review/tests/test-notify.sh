#!/usr/bin/env bash
# Slack notification: PR text is data — never expanded by a shell, never able to break the message.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"; export PRR_DIR="$T"
CANARY="$T/pwned"
python3 - "$T" "$CANARY" <<'PY'
import json, sys
t, canary = sys.argv[1:3]
json.dump({"title": f"fix: $(touch {canary}) `touch {canary}` <!channel> a|b"}, open(f"{t}/pr.json", "w"))
open(f"{t}/notify.md", "w").write(f"2 blocker(s):\n- crash in $(touch {canary})\n- <https://evil.example|click>")
PY
field() { python3 -c 'import json,sys; print(json.loads(sys.stdin.readline())[sys.argv[1]])' "$1"; }

OUT="$(PRR_NOTIFY_DRY=1 bash "$SCRIPTS/notify-block.sh" o/r 7 blocked "$T/notify.md")"
[ ! -e "$CANARY" ] || fail "PR title or summary was executed"; pass "title and summary are never executed"
[ "$(echo "$OUT" | field title)" = "🛑 PR blocked: o/r#7" ] || fail "title: $OUT"; pass "blocked title"
BODY="$(echo "$OUT" | field body)"
echo "$BODY" | grep -q '^<https://github.com/o/r/pull/7|fix: \$(touch ' || fail "link + literal title: $BODY"; pass "title kept as literal text"
[ "$(echo "$BODY" | grep -o '[<>|]' | wc -l)" = 3 ] || fail "only the one link may carry <, | and >: $BODY"; pass "Slack link syntax stripped from PR text"
echo "$BODY" | grep -q '/maestro approve' || fail "override hint"; pass "override hint"

OUT="$(PRR_NOTIFY_DRY=1 bash "$SCRIPTS/notify-block.sh" o/r 7 human "$T/notify.md")"
[ "$(echo "$OUT" | field title)" = "🙋 PR needs a human approve: o/r#7" ] || fail "human title"; pass "human kind"
OUT="$(PRR_NOTIFY_DRY=1 bash "$SCRIPTS/notify-block.sh" o/r 7 unreviewed)"
echo "$OUT" | field body | grep -q '/maestro review' || fail "unreviewed without summary"; pass "unreviewed kind, no summary file"

OUT="$(SHADOW=1 bash "$SCRIPTS/notify-block.sh" o/r 7 blocked "$T/notify.md")"; RC=$?
[ $RC -eq 0 ] && echo "$OUT" | grep -q '^NOTIFY=skipped$' || fail "shadow should skip"; pass "shadow mode → skipped"
OUT="$(bash "$SCRIPTS/notify-block.sh" 'o/r; rm -rf x' 7 blocked)"; RC=$?
[ $RC -eq 0 ] && echo "$OUT" | grep -q '^NOTIFY=failed$' || fail "bad repo should fail soft"; pass "bad repo → failed, exit 0"
OUT="$(bash "$SCRIPTS/notify-block.sh" o/r 7 nope)"; RC=$?
[ $RC -eq 0 ] && echo "$OUT" | grep -q '^NOTIFY=failed$' || fail "bad kind should fail soft"; pass "bad kind → failed, exit 0"
# Slack helper missing or broken must not fail the run
OUT="$(HOME="$T" PRR_PM_SHARED="$T/nowhere" bash "$SCRIPTS/notify-block.sh" o/r 7 blocked "$T/notify.md")"; RC=$?
[ $RC -eq 0 ] && echo "$OUT" | grep -q '^NOTIFY=\(failed\|sent\)$' || fail "missing helper: rc=$RC $OUT"; pass "exit 0 whatever Slack does"
mkdir -p "$T/pm"; echo 'slack_post() { printf "%s\n" "$@" > "$PRR_DIR/sent.txt"; }' > "$T/pm/context.sh"
OUT="$(PRR_PM_SHARED="$T/pm" bash "$SCRIPTS/notify-block.sh" o/r 7 blocked "$T/notify.md")"
echo "$OUT" | grep -q '^NOTIFY=sent$' && grep -q '^pr-auto-review$' "$T/sent.txt" || fail "should post through slack_post: $OUT"; pass "posts through slack_post"
[ ! -e "$CANARY" ] || fail "PR text executed on the real post path"; pass "real post path does not execute PR text"
echo "ALL PASS"
OUT="$(PRR_NOTIFY_DRY=1 bash "$SCRIPTS/notify-block.sh" o/r 7 failed "$T/notify.md")"
[ "$(echo "$OUT" | field title)" = "⚠️ PR review did not run: o/r#7" ] || fail "failed title"; pass "failed kind"
