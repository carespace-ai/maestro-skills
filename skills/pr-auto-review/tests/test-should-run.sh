#!/usr/bin/env bash
# Guard tests — no network: bot login, reviews and permission come from test seams.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
export PRR_BOT_LOGIN=maestro-bot
NONE="$(reviews)"

guard() {  # guard <payload-json> [reviews-file] → guard output
  CLAUDEHUB_INPUT_KWARGS="$1" PRR_REVIEWS_FILE="${2:-$NONE}" bash "$SCRIPTS/should-run.sh"
}
expect() {  # expect <name> <output> <DECISION> [MODE]
  echo "$2" | grep -q "^DECISION=$3$" || fail "$1: expected DECISION=$3, got: $(echo "$2" | tr '\n' ' ')"
  [ -z "${4:-}" ] || echo "$2" | grep -q "^MODE=$4$" || fail "$1: expected MODE=$4, got: $(echo "$2" | tr '\n' ' ')"
  pass "$1"
}

expect "opened → full"            "$(guard "$(cat "$FIX/pr-opened.json")")" RUN full
expect "ready_for_review → full"  "$(guard "$(mutate pr-opened.json 'p["action"]="ready_for_review"')")" RUN full
expect "empty payload"            "$(CLAUDEHUB_INPUT_KWARGS= bash "$SCRIPTS/should-run.sh")" SKIP
expect "closed action"            "$(guard "$(mutate pr-opened.json 'p["action"]="closed"')")" SKIP
expect "draft"                    "$(guard "$(mutate pr-opened.json 'p["pull_request"]["draft"]=True')")" SKIP

# release-please — each signal alone must skip
expect "release-please branch"    "$(guard "$(mutate pr-opened.json 'p["pull_request"]["head"]["ref"]="release-please--branches--main"')")" SKIP
expect "release-please label"     "$(guard "$(mutate pr-opened.json 'p["pull_request"]["labels"]=[{"name":"autorelease: pending"}]')")" SKIP
expect "release-please author"    "$(guard "$(mutate pr-opened.json 'p["pull_request"]["user"]["login"]="release-please[bot]"')")" SKIP

# automation
expect "own PR (self-approval)"   "$(guard "$(mutate pr-opened.json 'p["pull_request"]["user"]["login"]="maestro-bot"')")" SKIP
expect "dependabot"               "$(guard "$(mutate pr-opened.json 'p["pull_request"]["user"]["login"]="dependabot[bot]"')")" SKIP
expect "pipeline branch"          "$(guard "$(mutate pr-opened.json 'p["pull_request"]["head"]["ref"]="pipeline/issue-7-20261030"')")" SKIP
expect "context-layer branch"     "$(guard "$(mutate pr-opened.json 'p["pull_request"]["head"]["ref"]="claude/context-layer"')")" SKIP

# allowlist (shadow rollout)
expect "allowlist hit"            "$(guard "$(mutate pr-opened.json 'p["prr_repos"]=["carespace-api"]')")" RUN full
expect "allowlist miss"           "$(guard "$(mutate pr-opened.json 'p["prr_repos"]=["carespace-ui"]')")" SKIP
OUT="$(guard "$(mutate pr-opened.json 'p["prr_shadow"]=True')")"
echo "$OUT" | grep -q '^SHADOW=1$' || fail "prr_shadow should set SHADOW=1"; pass "shadow flag"

# idempotency — same head SHA already reviewed
DUP="$(mktemp)"; echo '[{"state":"APPROVED","user":{"login":"maestro-bot"},"body":"ok <!-- maestro-pr-review sha=aaaaaaa1111111111111111111111111111111aa verdict=APPROVE -->"}]' > "$DUP"
expect "duplicate delivery"       "$(guard "$(cat "$FIX/pr-opened.json")" "$DUP")" SKIP

# synchronize: every new head gets a review (stale approvals are dismissed on
# push); a PR the bot blocked only gets its blockers rechecked; an overridden
# PR is left alone
SYNC="$(mutate pr-opened.json 'p["action"]="synchronize"')"
expect "sync, never reviewed"     "$(guard "$SYNC")" RUN full
expect "sync, approved → re-review" "$(guard "$SYNC" "$(reviews APPROVED)")" RUN full
expect "sync, blocked → recheck"  "$(guard "$SYNC" "$(reviews CHANGES_REQUESTED)")" RUN recheck
expect "sync, block dismissed"    "$(guard "$SYNC" "$(reviews DISMISSED:REQUEST_CHANGES)")" SKIP
# "dismiss stale approvals on push": the bot's own approve turns DISMISSED on the
# next push. That is not a human override — the new head must be reviewed.
expect "sync, stale approve dismissed → review the push" "$(guard "$SYNC" "$(reviews DISMISSED:APPROVE)")" RUN delta
expect "sync, block fixed, approve went stale" "$(guard "$SYNC" "$(reviews CHANGES_REQUESTED:REQUEST_CHANGES DISMISSED:APPROVE)")" RUN delta
# delta: a push on a PR whose latest review was clean is reviewed from that commit
OUT="$(guard "$SYNC" "$(reviews APPROVED:APPROVE)")"
expect "sync, approved with marker → delta" "$OUT" RUN delta
echo "$OUT" | grep -q '^DELTA_BASE=00c0ffee$' || fail "delta should report DELTA_BASE (got: $OUT)"; pass "delta reports its base commit"
OUT="$(guard "$SYNC" "$(reviews APPROVED:APPROVE COMMENTED:APPROVE)")"
echo "$OUT" | grep -q '^DELTA_BASE=01c0ffee$' || fail "delta base is the latest clean read (got: $OUT)"; pass "delta base is the latest clean read"
expect "sync, held approve (CI) still a clean read" "$(guard "$SYNC" "$(reviews 'COMMENTED:APPROVE held=ci ci=failure')")" RUN delta
expect "sync, unread diff is not a base" "$(guard "$SYNC" "$(reviews APPROVED:APPROVE 'COMMENTED:APPROVE held=unread')")" RUN full
expect "sync, UNREVIEWED is not a base" "$(guard "$SYNC" "$(reviews APPROVED:APPROVE COMMENTED:UNREVIEWED)")" RUN full
expect "opened never uses delta"  "$(guard "$(mutate pr-opened.json 'p["action"]="reopened"')" "$(reviews DISMISSED:APPROVE)")" RUN full
expect "sync, dismissed without marker → re-review" "$(guard "$SYNC" "$(reviews DISMISSED)")" RUN full
expect "sync, comment after block" "$(guard "$SYNC" "$(reviews CHANGES_REQUESTED COMMENTED)")" RUN recheck
expect "reopened, blocked → recheck" "$(guard "$(mutate pr-opened.json 'p["action"]="reopened"')" "$(reviews CHANGES_REQUESTED)")" RUN recheck

# override — comment
BLOCKED="$(reviews CHANGES_REQUESTED)"
expect "/maestro approve (write)" "$(PRR_PERMISSION=write guard "$(cat "$FIX/comment-approve.json")" "$BLOCKED")" RUN override
expect "/maestro approve (read)"  "$(PRR_PERMISSION=read guard "$(cat "$FIX/comment-approve.json")" "$BLOCKED")" SKIP
expect "/maestro approve, not blocked" "$(PRR_PERMISSION=write guard "$(cat "$FIX/comment-approve.json")" "$(reviews APPROVED)")" SKIP
expect "ordinary comment"         "$(PRR_PERMISSION=write guard "$(mutate comment-approve.json 'p["comment"]["body"]="lgtm"')" "$BLOCKED")" SKIP
expect "comment on issue"         "$(PRR_PERMISSION=write guard "$(mutate comment-approve.json 'del p["issue"]["pull_request"]')" "$BLOCKED")" SKIP
OUT="$(PRR_PERMISSION=admin guard "$(cat "$FIX/comment-approve.json")" "$BLOCKED")"
echo "$OUT" | grep -q '^OVERRIDE_BY=dev-bob$' || fail "override should report OVERRIDE_BY"; pass "override reports who"

# /maestro review — fresh review of the current head, even if already reviewed
PRF="$(mktemp)"; python3 -c 'import json,sys; json.dump(json.load(open(sys.argv[1]))["pull_request"], open(sys.argv[2],"w"))' "$FIX/pr-opened.json" "$PRF"
REVIEW="$(mutate comment-approve.json 'p["comment"]["body"]="/maestro review"')"
expect "/maestro review (write)"  "$(PRR_PERMISSION=write PRR_PR_FILE="$PRF" guard "$REVIEW")" RUN full
expect "/maestro review, same SHA" "$(PRR_PERMISSION=write PRR_PR_FILE="$PRF" guard "$REVIEW" "$DUP")" RUN full
expect "/maestro review, blocked" "$(PRR_PERMISSION=write PRR_PR_FILE="$PRF" guard "$REVIEW" "$BLOCKED")" RUN recheck
expect "/maestro review (read)"   "$(PRR_PERMISSION=read PRR_PR_FILE="$PRF" guard "$REVIEW")" SKIP
DRAFT="$(mktemp)"; python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); p["draft"]=True; json.dump(p, open(sys.argv[2],"w"))' "$PRF" "$DRAFT"
expect "/maestro review on draft" "$(PRR_PERMISSION=write PRR_PR_FILE="$DRAFT" guard "$REVIEW")" SKIP
OUT="$(PRR_PERMISSION=write PRR_PR_FILE="$PRF" guard "$REVIEW")"
echo "$OUT" | grep -q '^HEAD_SHA=aaaaaaa' || fail "/maestro review should report HEAD_SHA"; pass "/maestro review reports head"

# override — label
LABEL='p["action"]="labeled"; p["label"]={"name":"maestro:override"}; p["sender"]={"login":"lead-carol"}'
expect "maestro:override label (write)" "$(PRR_PERMISSION=write guard "$(mutate pr-opened.json "$LABEL")" "$BLOCKED")" RUN override
expect "maestro:override label (triage)" "$(PRR_PERMISSION=triage guard "$(mutate pr-opened.json "$LABEL")" "$BLOCKED")" SKIP
expect "other label"              "$(guard "$(mutate pr-opened.json 'p["action"]="labeled"; p["label"]={"name":"bug"}')" "$BLOCKED")" SKIP

# run.env — later steps run in separate shells and source this instead of re-parsing
OUT="$(guard "$(mutate pr-opened.json 'p["pull_request"]["title"]="x $(touch /tmp/prr-pwned) y"')")"
RUN_ENV="$(echo "$OUT" | sed -n 's/^RUN_ENV=//p')"
[ -f "$RUN_ENV" ] || fail "guard should print RUN_ENV"
( source "$RUN_ENV"
  [ "$DECISION" = RUN ] && [ "$MODE" = full ] && [ -n "$HEAD_SHA" ] && [ -d "$S" ] || exit 1
  [ "$PRR_DIR" = "/tmp/prr-${REPO_FULL##*/}-$PR_NUMBER" ] || exit 1
  [ "$REASON" = "PR opened" ] ) || fail "run.env should carry the guard output, quoted"
pass "run env sourced (values with spaces survive)"
grep -q 'TITLE\|pwned' "$RUN_ENV" && fail "PR title must never reach run.env"; pass "PR title is not exported"

echo "ALL PASS"
