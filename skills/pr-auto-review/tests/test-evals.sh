#!/usr/bin/env bash
# Eval set: cases.json is well-formed, and the grader tells a caught defect from a miss.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"; export PRR_EVAL_HOME="$T"
G="$SCRIPTS/eval-grade.py"

python3 "$G" --check | grep -q '^OK=' || fail "shipped cases.json must validate: $(python3 "$G" --check)"; pass "shipped cases validate"

# payload <case-id> <verdict> <body text> [comment body]
payload() {
  mkdir -p "$T/$1"
  python3 - "$T/$1/payload.json" "$2" "$3" "${4:-}" <<'PY'
import json, sys
out, verdict, text, comment = sys.argv[1:5]
p = {"event": "COMMENT", "body": f"{text}\n\n<!-- maestro-pr-review sha=abc1234 verdict={verdict} -->"}
if comment:
    p["comments"] = [{"path": "src/x.py", "line": 3, "body": comment}]
json.dump(p, open(out, "w"))
PY
}
outcome() { python3 "$G" "$1" | awk 'NR==1 {print $NF}'; }
BUG=mobile-552-neck-rest-window; PRE=agent-18-voice-delete-substring; CTRL=agent-19-control

payload $BUG REQUEST_CHANGES "1 blocker" "the rest pitch is a rolling window of the last frames"
[ "$(outcome $BUG)" = caught ] || fail "blocked + named → caught (got $(outcome $BUG))"; pass "blocked and named → caught"
payload $BUG REQUEST_CHANGES "1 blocker" "the token is logged"
[ "$(outcome $BUG)" = wrong-reason ] || fail "blocked for something else → wrong-reason"; pass "blocked for something else → wrong-reason"
payload $BUG APPROVE "Reads neck pitch. Heads-up: the calibration frames may already hold the moved head."
[ "$(outcome $BUG)" = flagged ] || fail "approved with the defect named → flagged"; pass "approved but named → flagged"
payload $BUG APPROVE "Reads neck pitch."
[ "$(outcome $BUG)" = missed ] || fail "approved silently → missed"; pass "approved silently → missed"
python3 "$G" $BUG >/dev/null && fail "a miss must exit non-zero"; pass "a miss fails the run"
payload $BUG UNREVIEWED "could not read the diff"
[ "$(outcome $BUG)" = unreviewed ] || fail "UNREVIEWED → unreviewed"; pass "unreadable diff → unreviewed"

payload $CTRL APPROVE "Whole-word match."
[ "$(outcome $CTRL)" = clean ] || fail "control approved → clean"; pass "control approved → clean"
python3 "$G" $CTRL >/dev/null || fail "a clean control must exit 0"; pass "a clean control passes"
payload $CTRL REQUEST_CHANGES "1 blocker" "substring"
[ "$(outcome $CTRL)" = false-block ] || fail "control blocked → false-block"; pass "control blocked → false-block"

payload $PRE APPROVE "Tightens confirmation. Heads-up: the name is still a substring match."
[ "$(outcome $PRE)" = noted ] || fail "preexisting approved + named → noted"; pass "older defect named in an approve → noted"
python3 "$G" $PRE >/dev/null || fail "noted must exit 0"; pass "noted passes"
payload $PRE APPROVE "Tightens confirmation."
[ "$(outcome $PRE)" = clean ] || fail "preexisting approved silently → clean"; pass "older defect not mentioned → clean"
payload $PRE REQUEST_CHANGES "1 blocker" "substring match"
[ "$(outcome $PRE)" = false-block ] || fail "preexisting blocked → false-block"; pass "blocking for an older defect → false-block"
rm -rf "$T/$PRE"

rm -rf "$T/$BUG"
[ "$(outcome $BUG)" = no-payload ] || fail "missing payload → no-payload"; pass "case not run → no-payload"
SUM="$(python3 "$G" | tail -1)"   # exits 1 here (the control is a false-block) — capture, don't pipe
echo "$SUM" | grep -q '^SUMMARY bugs_caught=0/0 .*controls_clean=0/1 not_run=4$' || fail "summary line (got: $SUM)"; pass "summary counts"

# a malformed case file is refused
printf '{"cases":[{"id":"Bad Id","kind":"bug","repo":"o/r","pr":"1","base_sha":"x","head_sha":"y","expect":{"verdict":"APPROVE"}}]}' > "$T/bad.json"
OUT="$(PRR_EVAL_CASES="$T/bad.json" python3 "$G" --check)"; [ $? -eq 2 ] || fail "bad cases must exit 2"
echo "$OUT" | grep -q 'ERROR=.*40-character' || fail "bad sha reported"; pass "malformed cases refused"
OUT="$(PRR_EVAL_CASES="$T/bad.json" bash "$SCRIPTS/eval-stage.sh" nope)"; echo "$OUT" | grep -q '^ERROR=unknown or malformed case' || fail "eval-stage unknown case"; pass "eval-stage refuses an unknown case"
# eval-run.sh: stages, reviews and grades with one command (reviewer and staging stubbed)
R="$SCRIPTS/eval-run.sh"; B="$T/bin"; mkdir -p "$B"; rm -rf "$T/$CTRL"
cat > "$B/stage" <<'SH'
#!/usr/bin/env bash
rm -rf "$PRR_EVAL_HOME/$1"; mkdir -p "$PRR_EVAL_HOME/$1" && echo "export PRR_DIR=$PRR_EVAL_HOME/$1" > "$PRR_EVAL_HOME/$1/run.env"
SH
cat > "$B/reviewer" <<'SH'
#!/usr/bin/env bash
# stub reviewer: approves; records whether the answers were reachable from the skill copy
while [ $# -gt 0 ]; do [ "$1" = "--add-dir" ] && SKILL_COPY="$2"; shift; done
[ -e "$SKILL_COPY/evals/cases.json" ] && touch "$PRR_EVAL_HOME/leak"
[ -f "$SKILL_COPY/SKILL.md" ] && [ -f "$SKILL_COPY/evals/RUNNER.md" ] || exit 3
[ -n "${STUB_SILENT:-}" ] && exit 0
printf '{"event":"APPROVE","body":"ok\\n\\n<!-- maestro-pr-review sha=abc1234 verdict=APPROVE -->"}' > payload.json
SH
chmod +x "$B/stage" "$B/reviewer"
OUT="$(PRR_EVAL_STAGE="$B/stage" PRR_EVAL_CLAUDE="$B/reviewer" bash "$R" $CTRL)" || fail "eval-run on a clean control must exit 0 (got: $OUT)"
echo "$OUT" | grep -q "^$CTRL: reviewed$" || fail "eval-run reports the review (got: $OUT)"
echo "$OUT" | grep -q "clean$" || fail "eval-run grades the case (got: $OUT)"; pass "eval-run stages, reviews and grades"
[ -e "$T/leak" ] && fail "the reviewer's skill copy must not hold cases.json"; pass "reviewer copy has no answers"
OUT="$(PRR_EVAL_STAGE="$B/stage" PRR_EVAL_CLAUDE="$B/reviewer" bash "$R" $BUG)"; [ $? -eq 1 ] || fail "a missed bug must exit 1 (got: $OUT)"; pass "eval-run fails on a miss"
OUT="$(STUB_SILENT=1 PRR_EVAL_STAGE="$B/stage" PRR_EVAL_CLAUDE="$B/reviewer" bash "$R" $CTRL)"; [ $? -eq 2 ] || fail "no payload must exit 2 (got: $OUT)"
echo "$OUT" | grep -q "^NOT_REVIEWED=$CTRL" || fail "eval-run names the case that was not reviewed"; pass "eval-run reports a review that produced nothing"
OUT="$(PRR_EVAL_CLAUDE="$B/reviewer" bash "$R" nope 2>&1)"; [ $? -eq 2 ] || fail "unknown case must exit 2"; pass "eval-run refuses an unknown case"
echo "ALL PASS"
