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
#   diff.patch         full unified diff (rebuilt from per-file patches when the
#                      whole-PR diff is too large for GitHub to serve)
#   diff-unread.txt    text files whose patch could not be fetched (read them at HEAD)
#   context-layer.md   Context Layer nodes (AGENTS.md) read at BASE_SHA — root in
#                      full, nearest nodes in full while they fit, the rest excerpted
#   nodes/             full text of every staged node (for the excerpted ones)
#   profile.md         the repo's review profile (repos/<repo>/review.md) + the
#                      checklist of each stack the changed files belong to
#   risk-files.txt     changed files on a risk path — read in full, never skimmed
#   status.env         DIFF_STATUS / CONTEXT_STATUS — post-review.sh refuses to
#                      APPROVE a PR whose diff could not be read
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
MAX_NODES="${PRR_MAX_NODES:-12}"        # nodes fetched per PR (budgets: context-assemble.py)
rm -rf "$DIR"; mkdir -p "$DIR/nodes"
# Fail closed: until the diff is staged, this PR counts as unreadable.
printf 'DIFF_STATUS=missing\nCONTEXT_STATUS=error\n' > "$DIR/status.env"

gh pr view "$PR" --repo "$REPO" \
  --json number,title,body,author,labels,additions,deletions,changedFiles,headRefOid,baseRefName,closingIssuesReferences \
  > "$DIR/pr.json" || { echo "ERROR=cannot read PR $REPO#$PR"; exit 1; }

# Changed files (with per-file patches) — one retry, the list drives everything below
for _try in 1 2; do
  gh api --paginate "repos/$REPO/pulls/$PR/files?per_page=100" > "$DIR/.files.json" 2> "$DIR/.files.err" && break
  sleep 2
done
python3 "$HERE/diff-fallback.py" --names "$DIR/.files.json" > "$DIR/files.txt" 2>/dev/null
CHANGED="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("changedFiles",0))' "$DIR/pr.json" 2>/dev/null || echo 0)"

# Diff — the whole-PR diff when GitHub serves it, else stitched from per-file patches.
# Never leave an empty diff looking like "nothing to flag".
: > "$DIR/diff-unread.txt"
if gh pr diff "$PR" --repo "$REPO" > "$DIR/diff.patch" 2> "$DIR/.diff.err" && [ -s "$DIR/diff.patch" ]; then
  DIFF_STATUS=ok; DIFF_UNREAD=0
elif [ "$CHANGED" = "0" ] && [ ! -s "$DIR/files.txt" ] && [ ! -s "$DIR/.files.err" ]; then
  DIFF_STATUS=ok; DIFF_UNREAD=0          # genuinely empty PR
else
  FB="$(python3 "$HERE/diff-fallback.py" "$DIR/.files.json" "$DIR/diff.patch" "$DIR/diff-unread.txt" "$CHANGED" 2>/dev/null)"
  DIFF_STATUS="$(echo "$FB" | sed -n 's/^DIFF_STATUS=//p')"; DIFF_UNREAD="$(echo "$FB" | sed -n 's/^DIFF_UNREAD=//p')"
  DIFF_STATUS="${DIFF_STATUS:-missing}"; DIFF_UNREAD="${DIFF_UNREAD:-0}"
fi
gh pr checks "$PR" --repo "$REPO" > "$DIR/ci.txt" 2>&1 || true

# Linked issues — first 3, bodies capped
: > "$DIR/linked-issues.md"
python3 -c 'import json,sys; [print(i["number"]) for i in json.load(open(sys.argv[1])).get("closingIssuesReferences",[])[:3]]' "$DIR/pr.json" |
while read -r n; do
  gh issue view "$n" --repo "$REPO" --json number,title,body \
    --jq '"## #\(.number) \(.title)\n\n\(.body // "" | .[0:2000])\n"' >> "$DIR/linked-issues.md" 2>/dev/null
done

# Context Layer — pick nodes from the base tree (priority order), stage each one in
# full under nodes/, then let context-assemble.py decide what is inlined vs excerpted.
CONTEXT_STATUS=ok
for _try in 1 2; do
  gh api "repos/$REPO/git/trees/$BASE_SHA?recursive=1" \
    --jq '.tree[] | select(.type=="blob") | .path' > "$DIR/.tree.txt" 2>/dev/null && break
  : > "$DIR/.tree.txt"; CONTEXT_STATUS=error; sleep 2
done
[ -s "$DIR/.tree.txt" ] && CONTEXT_STATUS=ok
: > "$DIR/.nodes.tsv"; i=0; NODES_DROPPED=0
while read -r node; do
  [ -n "$node" ] || continue
  if [ "$i" -ge "$MAX_NODES" ]; then NODES_DROPPED=$((NODES_DROPPED + 1)); continue; fi
  f="$DIR/nodes/$(printf '%02d' "$i")-$(echo "$node" | tr '/' '_')"
  gh api "repos/$REPO/contents/$node?ref=$BASE_SHA" -H 'Accept: application/vnd.github.raw' > "$f" 2>/dev/null \
    && [ -s "$f" ] || { rm -f "$f"; continue; }
  printf '%s\t%s\n' "$node" "$f" >> "$DIR/.nodes.tsv"; i=$((i + 1))
done < <(python3 "$HERE/context-nodes.py" "$DIR/files.txt" "$DIR/.tree.txt")
ASM="$(python3 "$HERE/context-assemble.py" "$DIR/.nodes.tsv" "$DIR/context-layer.md" "$BASE_SHA")" \
  || { : > "$DIR/context-layer.md"; ASM=$'CONTEXT_NODES=0\nCONTEXT_NODES_EXCERPTED=0'; CONTEXT_STATUS=error; }
[ "$CONTEXT_STATUS" = ok ] && [ "$i" -eq 0 ] && CONTEXT_STATUS=none

# Review profile — repo notes + stack checklists + the risk files of this PR
PROF="$(python3 "$HERE/resolve-profile.py" "$REPO" "$DIR/files.txt" "$DIR" 2>/dev/null)" \
  || { PROF=$'PROFILE=error\nSTACKS=\nRISK_FILES=0\nCI_IGNORE='; : > "$DIR/profile.md"; : > "$DIR/risk-files.txt"; }
CI_IGNORE="$(echo "$PROF" | sed -n 's/^CI_IGNORE=//p')"

printf 'DIFF_STATUS=%s\nDIFF_UNREAD=%s\nCONTEXT_STATUS=%s\nCI_IGNORE=%s\n' \
  "$DIFF_STATUS" "$DIFF_UNREAD" "$CONTEXT_STATUS" "$CI_IGNORE" > "$DIR/status.env"

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
echo "DIFF_STATUS=$DIFF_STATUS"
echo "DIFF_UNREAD=$DIFF_UNREAD"
echo "CONTEXT_STATUS=$CONTEXT_STATUS"
echo "$ASM" | grep -E '^CONTEXT_NODES(_EXCERPTED)?='
echo "CONTEXT_NODES_DROPPED=$NODES_DROPPED"
echo "$PROF" | grep -E '^(PROFILE|STACKS|RISK_FILES)='
echo "LINKED_ISSUES=$(grep -c '^## #' "$DIR/linked-issues.md")"
echo "HAS_PRIOR_BLOCKERS=$([ -s "$DIR/prior-blockers.md" ] && echo 1 || echo 0)"
