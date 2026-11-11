#!/usr/bin/env bash
# Run the eval set end to end: stage each case, have a headless reviewer review
# it in dry-run, grade the results. Nothing is posted to GitHub or Slack.
#
# Usage: eval-run.sh [--jobs N] [case-id ...]      (default: every case, 2 at a time)
#
# Env:
#   PRR_EVAL_HOME     where cases are staged        (default ~/.prr/evals)
#   PRR_EVAL_MODEL    model for the reviewer        (default: the CLI's default)
#   PRR_EVAL_TIMEOUT  seconds per review            (default 1500)
#   PRR_EVAL_CLAUDE   reviewer CLI                  (default claude)
#   PRR_EVAL_STAGE    staging script, for tests     (default eval-stage.sh)
#
# The reviewer works from a copy of the skill that has no evals/cases.json, so
# the answers are not on its disk.
#
# Exit code: 0 when every case is caught / clean / noted, 1 otherwise, 2 on bad
# usage or when a case could not be staged or reviewed.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="$(cd "$HERE/.." && pwd)"
export PRR_EVAL_CASES="${PRR_EVAL_CASES:-$SKILL/evals/cases.json}"
export PRR_EVAL_HOME="${PRR_EVAL_HOME:-$HOME/.prr/evals}"
CLAUDE="${PRR_EVAL_CLAUDE:-claude}"
TIMEOUT="${PRR_EVAL_TIMEOUT:-1500}"
JOBS=2
IDS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --jobs) JOBS="${2:-}"; shift 2 || { echo "Usage: eval-run.sh [--jobs N] [case-id ...]" >&2; exit 2; } ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    -*) echo "ERROR=unknown option $1" >&2; exit 2 ;;
    *) IDS+=("$1"); shift ;;
  esac
done
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo "ERROR=--jobs needs a positive number" >&2; exit 2; }
command -v "$CLAUDE" >/dev/null || { echo "ERROR=$CLAUDE not found" >&2; exit 2; }

ALL="$(bash "$HERE/eval-stage.sh" --list | cut -f1)" || exit 2
if [ ${#IDS[@]} -eq 0 ]; then
  mapfile -t IDS <<< "$ALL"
else
  for id in "${IDS[@]}"; do
    grep -qxF -- "$id" <<< "$ALL" || { echo "ERROR=unknown case: $id" >&2; exit 2; }
  done
fi

# Blind copy of the skill: everything a reviewer may read, without the answers.
BLIND="$(mktemp -d)"; trap 'rm -rf "$BLIND"' EXIT
mkdir -p "$BLIND/evals"
cp -R "$SKILL/SKILL.md" "$SKILL/REFERENCE.md" "$SKILL/relations.json" \
      "$SKILL/repos" "$SKILL/stacks" "$SKILL/scripts" "$SKILL/templates" "$BLIND/" || exit 2
cp "$SKILL/evals/RUNNER.md" "$BLIND/evals/" || exit 2
mkdir -p "$PRR_EVAL_HOME"

run_case() {
  local id="$1" dir="$PRR_EVAL_HOME/$1" log="$PRR_EVAL_HOME/$1.log"
  if ! bash "${PRR_EVAL_STAGE:-$BLIND/scripts/eval-stage.sh}" "$id" > "$log" 2>&1; then
    echo "$id: staging failed (see $log)"; return 1
  fi
  local prompt="You are running one eval case of the pr-auto-review skill.
The skill is at $BLIND (SKILL.md, REFERENCE.md, stacks/, repos/, scripts/).
Read $BLIND/evals/RUNNER.md and follow it exactly, with RUN_ENV=$dir/run.env .
When payload.json is written, stop."
  local args=(-p "$prompt" --allowedTools Bash Read Write Glob Grep --add-dir "$BLIND")
  [ -n "${PRR_EVAL_MODEL:-}" ] && args+=(--model "$PRR_EVAL_MODEL")
  ( cd "$dir" && timeout "$TIMEOUT" "$CLAUDE" "${args[@]}" < /dev/null ) >> "$log" 2>&1
  local rc=$?
  if [ ! -s "$dir/payload.json" ]; then
    echo "$id: no review produced (reviewer exit $rc, see $log)"; return 1
  fi
  echo "$id: reviewed"
}

FAILED="$(mktemp)"; : > "$FAILED"
for id in "${IDS[@]}"; do
  while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
  { run_case "$id" || echo "$id" >> "$FAILED"; } &
done
wait

echo
GRADE_RC=0
if [ ${#IDS[@]} -eq 1 ]; then
  python3 "$HERE/eval-grade.py" "${IDS[0]}" || GRADE_RC=$?
else
  python3 "$HERE/eval-grade.py" || GRADE_RC=$?
fi
if [ -s "$FAILED" ]; then
  echo "NOT_REVIEWED=$(tr '\n' ' ' < "$FAILED")"; rm -f "$FAILED"; exit 2
fi
rm -f "$FAILED"
exit "$GRADE_RC"
