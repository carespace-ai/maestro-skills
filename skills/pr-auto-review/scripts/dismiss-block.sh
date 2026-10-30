#!/usr/bin/env bash
# dismiss-block.sh — human override: dismiss every active CHANGES_REQUESTED review
# the bot left on a PR, then leave a one-line acknowledgement. Never approves —
# the override unblocks the PR; it doesn't pretend the bot changed its mind.
#
# Usage: dismiss-block.sh <REPO_FULL> <PR_NUMBER> <BOT_LOGIN> <WHO>
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_auth.sh"

REPO="${1:?REPO_FULL}"; PR="${2:?PR_NUMBER}"; BOT="${3:?BOT_LOGIN}"; WHO="${4:?WHO}"
MSG="Overridden by @$WHO — Maestro review block dismissed."

IDS="$(gh api "repos/$REPO/pulls/$PR/reviews?per_page=100" \
  --jq ".[] | select(.user.login==\"$BOT\" and .state==\"CHANGES_REQUESTED\") | .id")"
[ -n "$IDS" ] || { echo "DISMISSED=0"; exit 0; }

N=0
for id in $IDS; do
  gh api "repos/$REPO/pulls/$PR/reviews/$id/dismissals" --method PUT \
    -f message="$MSG" -f event=DISMISS > /dev/null && N=$((N + 1))
done
gh pr comment "$PR" --repo "$REPO" \
  --body "🔓 $MSG The decision is yours — merge when ready. <!-- maestro-pr-review override -->" > /dev/null
echo "DISMISSED=$N"
