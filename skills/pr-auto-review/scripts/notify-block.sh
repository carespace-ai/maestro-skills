#!/usr/bin/env bash
# notify-block.sh — tell Slack about a PR the bot did not approve.
#
# Usage: notify-block.sh <REPO_FULL> <PR_NUMBER> <blocked|unreviewed|human|failed> [SUMMARY_FILE]
#
#   blocked      the bot requested changes   (summary = one line per blocker)
#   unreviewed   the diff could not be read  (summary = why)
#   human        the PR touches human-only paths and waits for a person
#   failed       a skill script failed, so no review was posted (summary = the ERROR= line)
#   SUMMARY_FILE plain text written by the skill; read as data, never by the shell
#
# The PR title is read from $PRR_DIR/pr.json — it is never passed on a command
# line or expanded by a shell, so a title like `$(…)` stays text. Title and
# summary are stripped of Slack link syntax and capped before posting.
#
# Does nothing in shadow mode (SHADOW=1). Never fails the run: exit code is
# always 0 and it prints NOTIFY=sent|skipped|failed (+ NOTIFY_REASON).
# PRR_PM_SHARED overrides where _pm-shared/context.sh is looked up.
# PRR_NOTIFY_DRY=1 prints the message instead of posting (tests).
set -uo pipefail
REPO="${1:-}"; PR="${2:-}"; KIND="${3:-}"; SUMMARY="${4:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
done_() { echo "NOTIFY=$1"; [ -z "${2:-}" ] || echo "NOTIFY_REASON=$2"; exit 0; }

[[ "$REPO" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ && "$PR" =~ ^[0-9]+$ ]] || done_ failed "bad repo or PR number"
case "$KIND" in blocked|unreviewed|human|failed) ;; *) done_ failed "unknown kind '$KIND'" ;; esac
[ "${SHADOW:-${PRR_SHADOW:-0}}" = "1" ] && done_ skipped "shadow mode"
DIR="${PRR_DIR:-/tmp/prr-${REPO##*/}-$PR}"

MSG="$(python3 - "$DIR/pr.json" "$SUMMARY" "$REPO" "$PR" "$KIND" <<'PY'
import json, re, sys
pr_file, summary_file, repo, number, kind = sys.argv[1:6]

def clean(text, cap):
    text = re.sub(r"[<>|`]", "", text or "")
    text = re.sub(r"[\x00-\x09\x0b-\x1f]", " ", text)
    return text.strip()[:cap]

try:
    title = clean(json.load(open(pr_file)).get("title"), 150).replace("\n", " ")
except Exception:
    title = ""
try:
    summary = clean(open(summary_file).read(), 900) if summary_file else ""
except Exception:
    summary = ""
link = f"<https://github.com/{repo}/pull/{number}|{title or f'{repo}#{number}'}>"
head, tail = {
    "blocked": (f"🛑 PR blocked: {repo}#{number}", "Override: comment `/maestro approve`."),
    "unreviewed": (f"👀 PR needs a human review: {repo}#{number}", "Retry: comment `/maestro review`."),
    "failed": (f"⚠️ PR review did not run: {repo}#{number}",
               "Nothing was posted on the PR. Fix the skill, then comment `/maestro review`."),
    "human": (f"🙋 PR needs a human approve: {repo}#{number}",
              "It changes files the bot never approves on its own."),
}[kind]
print(json.dumps({"title": head, "body": " — ".join(x for x in (link, summary, tail) if x)}))
PY
)" || done_ failed "could not build the message"
if [ "${PRR_NOTIFY_DRY:-0}" = "1" ]; then echo "$MSG"; done_ skipped "dry run"; fi

CTX=""
for c in "${PRR_PM_SHARED:-}" "$HOME/.claude/skills/_pm-shared" "$HERE/../../_pm-shared"; do
  [ -n "$c" ] && [ -f "$c/context.sh" ] && { CTX="$c/context.sh"; break; }
done
[ -n "$CTX" ] || CTX="$(find "$HOME/.claude/skills" /app -name context.sh -path '*_pm-shared*' 2>/dev/null | head -1)"
[ -n "$CTX" ] || done_ failed "_pm-shared/context.sh not found"

# Subshell: context.sh is not written for `set -u`, and nothing it does may end the run.
if ( set +u
     source "$CTX" >/dev/null 2>&1 || exit 1
     TITLE="$(printf '%s' "$MSG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["title"])')"
     BODY="$(printf '%s' "$MSG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["body"])')"
     slack_post "${SLACK_ENGINEERING:-#pm-engineering}" "$TITLE" "$BODY" "pr-auto-review" ) > /dev/null 2>&1; then
  done_ sent
fi
done_ failed "slack_post failed"
