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

# synchronize: only rechecks a PR the bot blocked (no infinite review loop)
SYNC="$(mutate pr-opened.json 'p["action"]="synchronize"')"
expect "sync, never reviewed"     "$(guard "$SYNC")" SKIP
expect "sync, approved"           "$(guard "$SYNC" "$(reviews APPROVED)")" SKIP
expect "sync, blocked → recheck"  "$(guard "$SYNC" "$(reviews CHANGES_REQUESTED)")" RUN recheck
expect "sync, block dismissed"    "$(guard "$SYNC" "$(reviews CHANGES_REQUESTED DISMISSED)")" SKIP
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

# override — label
LABEL='p["action"]="labeled"; p["label"]={"name":"maestro:override"}; p["sender"]={"login":"lead-carol"}'
expect "maestro:override label"   "$(guard "$(mutate pr-opened.json "$LABEL")" "$BLOCKED")" RUN override
expect "other label"              "$(guard "$(mutate pr-opened.json 'p["action"]="labeled"; p["label"]={"name":"bug"}')" "$BLOCKED")" SKIP

echo "ALL PASS"
