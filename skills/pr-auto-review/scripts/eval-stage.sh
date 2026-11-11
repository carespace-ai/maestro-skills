#!/usr/bin/env bash
# Stage one eval case: a historic PR from evals/cases.json, ready to be reviewed
# in dry-run (nothing is posted). Read-only against GitHub.
#
# Usage: eval-stage.sh <case-id> | --list
#
# Writes to $PRR_EVAL_HOME/<case-id>/ (default ~/.prr/evals/<case-id>/):
#   run.env        what the review steps source (PRR_DRY_RUN=1, MODE=full)
#   everything fetch-context.sh stages (diff.patch, context-layer.md, …)
#   payload.json   written later by the reviewer (see evals/RUNNER.md)
#
# Prints RUN_ENV=, PRR_DIR= and the fetch-context summary.
# The bot's earlier reviews of the PR are not staged (BOT_LOGIN is empty), so a
# case is always read cold.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASES="${PRR_EVAL_CASES:-$HERE/../evals/cases.json}"
[ $# -eq 1 ] || { echo "Usage: eval-stage.sh <case-id> | --list" >&2; exit 2; }

if [ "$1" = "--list" ]; then
  python3 - "$CASES" <<'PY'
import json, sys
for c in json.load(open(sys.argv[1]))["cases"]:
    print(f"{c['id']}\t{c['kind']}\t{c['repo']}#{c['pr']}")
PY
  exit 0
fi

FIELDS="$(python3 - "$CASES" "$1" <<'PY'
import json, re, sys
case = next((c for c in json.load(open(sys.argv[1]))["cases"] if c["id"] == sys.argv[2]), None)
if not case:
    sys.exit(1)
for k in ("repo", "pr", "base_sha", "head_sha"):
    v = str(case[k])
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", v):
        sys.exit(1)
    print(v)
PY
)" || { echo "ERROR=unknown or malformed case: $1"; exit 1; }
{ read -r REPO; read -r PR; read -r BASE; read -r HEAD; } <<< "$FIELDS"

DIR="${PRR_EVAL_HOME:-$HOME/.prr/evals}/$1"
rm -rf "$DIR"; mkdir -p "$DIR" || { echo "ERROR=cannot create $DIR"; exit 1; }
ENVTMP="$(mktemp)"; trap 'rm -f "$ENVTMP"' EXIT   # fetch-context.sh empties $DIR, so the env file lands there last

# The diff is fetched from the PR, so the PR must still be at the pinned commit.
LIVE="$(gh pr view "$PR" --repo "$REPO" --json headRefOid --jq .headRefOid 2>/dev/null)"
[ "$LIVE" = "$HEAD" ] || { echo "ERROR=$REPO#$PR head is '${LIVE:-unreadable}', case pins $HEAD"; exit 1; }

{
  printf 'export S=%q\n' "$HERE"
  printf 'export REPO_FULL=%q\nexport PR_NUMBER=%q\n' "$REPO" "$PR"
  printf 'export BASE_SHA=%q\nexport HEAD_SHA=%q\n' "$BASE" "$HEAD"
  printf 'export PRR_DIR=%q\n' "$DIR"
  printf 'export BOT_LOGIN=\nexport MODE=full\nexport SHADOW=0\n'
  printf 'export PRR_DRY_RUN=1\nexport PRR_NOTIFY_DRY=1\n'
} > "$ENVTMP"

# shellcheck disable=SC1091
source "$ENVTMP"
# Staging the other side of a contract clones over https and needs a token in the
# environment. On a laptop gh keeps it in the keyring: lend it to this process only
# (it is not written to run.env).
[ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ] || { GH_TOKEN="$(gh auth token 2>/dev/null)"; export GH_TOKEN; }
OUT="$(bash "$HERE/fetch-context.sh" "$REPO" "$PR" "$BASE" "")" || { echo "$OUT"; echo "ERROR=fetch-context failed"; exit 1; }
echo "$OUT"
cp "$ENVTMP" "$DIR/run.env" || { echo "ERROR=cannot write $DIR/run.env"; exit 1; }
echo "RUN_ENV=$DIR/run.env"
echo "CASE=$1"
