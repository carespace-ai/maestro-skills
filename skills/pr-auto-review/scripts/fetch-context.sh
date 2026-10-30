#!/usr/bin/env bash
# fetch-context.sh — stage everything the review needs for one PR into files,
# so the skill reads only what it needs instead of dumping API JSON into context.
#
# Usage: fetch-context.sh <REPO_FULL> <PR_NUMBER> <BASE_SHA> [BOT_LOGIN]
#
# Writes to $PRR_DIR (default /tmp/prr-<repo>-<pr>/):
#   pr.json            title, body, author, labels, size, head sha
#   linked-issues.md   bodies of the issues the PR closes (the PR's purpose)
#   files.txt          changed paths, one per line
#   diff.patch         full unified diff
#   context-layer.md   Context Layer nodes (AGENTS.md) read at BASE_SHA, budgeted
#   ci.txt             check status at fetch time (informational, often pending)
#   prior-blockers.md  body of the bot's latest CHANGES_REQUESTED review (if any)
#
# The Context Layer is read from the BASE sha on purpose: a PR must not be able
# to rewrite the reviewer's instructions by editing AGENTS.md in its own diff.
#
# Prints KEY=VALUE summary lines. Exits non-zero only if the PR itself can't be read.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_auth.sh"

REPO="${1:?REPO_FULL}"; PR="${2:?PR_NUMBER}"; BASE_SHA="${3:?BASE_SHA}"; BOT="${4:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${PRR_DIR:-/tmp/prr-${REPO##*/}-$PR}"
BUDGET="${PRR_CONTEXT_BUDGET:-32000}"   # chars ≈ 8k tokens
rm -rf "$DIR"; mkdir -p "$DIR"

gh pr view "$PR" --repo "$REPO" \
  --json number,title,body,author,labels,additions,deletions,changedFiles,headRefOid,baseRefName,closingIssuesReferences \
  > "$DIR/pr.json" || { echo "ERROR=cannot read PR $REPO#$PR"; exit 1; }

gh api --paginate "repos/$REPO/pulls/$PR/files?per_page=100" --jq '.[].filename' > "$DIR/files.txt" 2>/dev/null
gh pr diff "$PR" --repo "$REPO" > "$DIR/diff.patch" 2>/dev/null
gh pr checks "$PR" --repo "$REPO" > "$DIR/ci.txt" 2>&1 || true

# Linked issues — first 3, bodies capped
: > "$DIR/linked-issues.md"
python3 -c 'import json,sys; [print(i["number"]) for i in json.load(open(sys.argv[1])).get("closingIssuesReferences",[])[:3]]' "$DIR/pr.json" |
while read -r n; do
  gh issue view "$n" --repo "$REPO" --json number,title,body \
    --jq '"## #\(.number) \(.title)\n\n\(.body // "" | .[0:2000])\n"' >> "$DIR/linked-issues.md" 2>/dev/null
done

# Context Layer — pick nodes from the base tree, load in priority order until the budget
gh api "repos/$REPO/git/trees/$BASE_SHA?recursive=1" \
  --jq '.tree[] | select(.type=="blob") | .path' > "$DIR/.tree.txt" 2>/dev/null
NODES=0; CHARS=0; SKIPPED=0
: > "$DIR/context-layer.md"
while read -r node; do
  [ -n "$node" ] || continue
  body="$(gh api "repos/$REPO/contents/$node?ref=$BASE_SHA" -H 'Accept: application/vnd.github.raw' 2>/dev/null)" || continue
  len=${#body}
  # Root always loads (truncated if needed); the rest only while they fit
  if [ "$NODES" -gt 0 ] && [ $((CHARS + len)) -gt "$BUDGET" ]; then SKIPPED=$((SKIPPED + 1)); continue; fi
  [ "$NODES" -eq 0 ] && [ "$len" -gt "$BUDGET" ] && body="${body:0:$BUDGET}" && len=$BUDGET
  printf '\n<!-- context-layer node: %s (base %s) -->\n%s\n' "$node" "${BASE_SHA:0:7}" "$body" >> "$DIR/context-layer.md"
  NODES=$((NODES + 1)); CHARS=$((CHARS + len))
done < <(python3 "$HERE/context-nodes.py" "$DIR/files.txt" "$DIR/.tree.txt")

# Prior blockers — what the bot asked for last time (recheck mode reads this)
: > "$DIR/prior-blockers.md"
if [ -n "$BOT" ]; then
  gh api "repos/$REPO/pulls/$PR/reviews?per_page=100" \
    --jq "[.[] | select(.user.login==\"$BOT\" and .state==\"CHANGES_REQUESTED\")] | last | .body // empty" \
    > "$DIR/prior-blockers.md" 2>/dev/null
fi

echo "PRR_DIR=$DIR"
echo "FILES=$(wc -l < "$DIR/files.txt" | tr -d ' ')"
echo "DIFF_LINES=$(wc -l < "$DIR/diff.patch" | tr -d ' ')"
echo "CONTEXT_NODES=$NODES"
echo "CONTEXT_NODES_SKIPPED=$SKIPPED"
echo "LINKED_ISSUES=$(grep -c '^## #' "$DIR/linked-issues.md")"
echo "HAS_PRIOR_BLOCKERS=$([ -s "$DIR/prior-blockers.md" ] && echo 1 || echo 0)"
