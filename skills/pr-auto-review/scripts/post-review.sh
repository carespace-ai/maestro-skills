#!/usr/bin/env bash
# post-review.sh — publish exactly ONE review on a PR.
#
# Usage: post-review.sh <REPO_FULL> <PR_NUMBER> <HEAD_SHA> <APPROVE|REQUEST_CHANGES|UNREVIEWED> <BODY_FILE> [COMMENTS_JSON]
#
#   UNREVIEWED     the PR could not be read (diff unavailable) — posted as a COMMENT
#                  that says so; never counts as an approve
#
#   BODY_FILE      markdown review body written by the skill
#   COMMENTS_JSON  optional file: [{"path": "...", "line": 42, "body": "..."}] — blockers only,
#                  each anchored to a RIGHT-side line that exists in the diff
#
# Appends the hidden idempotency marker `<!-- maestro-pr-review sha=<HEAD_SHA> verdict=<V> -->`
# that should-run.sh uses to drop duplicate deliveries — never post a review without it.
# The review is pinned to HEAD_SHA (commit_id) so it can't land on a newer, unreviewed push.
#
# Nothing at all is posted when the PR head is no longer HEAD_SHA (status.env
# HEAD_MOVED=1 from fetch-context.sh, or a push that landed while the review was
# being written): an approve on an old commit still counts toward branch
# protection where stale approvals are not dismissed. Prints
# REVIEW_SKIPPED=head-moved; the run of the newer push reviews the PR.
# PRR_HEAD_NOW = test seam.
#
# An APPROVE is only ever posted for a PR that was actually read and is not red:
#   - status.env (written by fetch-context.sh next to BODY_FILE) must say the diff
#     was staged; DIFF_STATUS=missing, or no status.env at all → COMMENT, not approve
#   - a PR that changes a file on the repo profile's `human_paths` (status.env
#     HUMAN_FILES, list in human-files.txt) is never approved by the bot: the
#     findings go out as a COMMENT asking for a human approve. HUMAN_FILES absent
#     or "unknown" holds too — the gate fails closed.
#   - CI on HEAD_SHA is checked right before posting (waits up to PRR_CI_WAIT
#     seconds, default 60, for running checks). Failing → COMMENT "not approving
#     yet" (re-trigger: push, or comment `/maestro review` once CI is green).
#     Still running → APPROVE with a note that the checks were not finished.
#     Check names matching the repo profile's `ci_ignore` regex (status.env
#     CI_IGNORE; env PRR_CI_IGNORE overrides) never count. PRR_CI_FILE = test seam.
#
# SHADOW=1 (or PRR_SHADOW=1) downgrades the event to COMMENT — shadow-mode rollout.
# PRR_DRY_RUN=1 prints the payload instead of calling GitHub (tests).
# If GitHub rejects the inline comments (422: line not in diff), retries once with the
# comments folded into the body, so a bad anchor never loses the review.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_auth.sh"

REPO="${1:?REPO_FULL}"; PR="${2:?PR_NUMBER}"; SHA="${3:?HEAD_SHA}"
VERDICT="${4:?APPROVE|REQUEST_CHANGES}"; BODY_FILE="${5:?BODY_FILE}"; COMMENTS="${6:-}"
case "$VERDICT" in APPROVE|REQUEST_CHANGES|UNREVIEWED) ;; *) echo "ERROR=invalid verdict $VERDICT"; exit 2 ;; esac
SHADOW="${SHADOW:-${PRR_SHADOW:-0}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"

# ── Head moved — the review would land on a commit that is no longer the PR ──
STAGE="${PRR_DIR:-$(dirname "$BODY_FILE")}"
HEAD_NOW="${PRR_HEAD_NOW:-}"
if [ -z "$HEAD_NOW" ] && [ "${PRR_DRY_RUN:-0}" != "1" ]; then
  HEAD_NOW="$(gh api "repos/$REPO/pulls/$PR" --jq '.head.sha' 2>/dev/null)"
fi
if grep -q '^HEAD_MOVED=1$' "$STAGE/status.env" 2>/dev/null || { [ -n "$HEAD_NOW" ] && [ "$HEAD_NOW" != "$SHA" ]; }; then
  echo "REVIEW_SKIPPED=head-moved"; echo "HEAD_NOW=${HEAD_NOW:-unknown}"
  exit 0
fi

# ── Approve gates — decide HOLD (why an APPROVE must not be posted) and NOTE ──
HOLD=""; NOTE=""; CI_STATE=skipped
if [ "$VERDICT" = APPROVE ]; then
  STATUS_FILE="$STAGE/status.env"
  DIFF_STATUS="$(sed -n 's/^DIFF_STATUS=//p' "$STATUS_FILE" 2>/dev/null | head -1)"
  [ -n "${PRR_CI_IGNORE:-}" ] || export PRR_CI_IGNORE="$(sed -n 's/^CI_IGNORE=//p' "$STATUS_FILE" 2>/dev/null | head -1)"
  case "$DIFF_STATUS" in
    ok|partial) ;;
    *) HOLD="unread"
       NOTE="⏸️ **Not approved — I could not read this PR's diff** (\`DIFF_STATUS=${DIFF_STATUS:-unknown}\`), so nothing below is a review of the change. A human needs to review this one, or comment \`/maestro review\` to make me try again." ;;
  esac
  HUMAN_FILES="$(sed -n 's/^HUMAN_FILES=//p' "$STATUS_FILE" 2>/dev/null | head -1)"
  if [ -z "$HOLD" ] && [ "$HUMAN_FILES" != "0" ]; then
    HOLD="human"
    HUMAN_LIST="$(head -8 "$STAGE/human-files.txt" 2>/dev/null | sed 's/`//g; s/.*/`&`/' | paste -sd, - | sed 's/,/, /g')"
    case "$HUMAN_FILES" in
      ''|unknown) NOTE="⏸️ **Needs a human approve** — I could not work out whether this PR touches files that need one, so I am not approving it myself. The code review below found no blockers." ;;
      *) NOTE="⏸️ **Needs a human approve** — this PR changes ${HUMAN_FILES} file(s) I never approve on my own: ${HUMAN_LIST}$([ "$HUMAN_FILES" -gt 8 ] 2>/dev/null && echo ', …'). The code review below found no blockers; a person with write access has to approve this one." ;;
    esac
  fi
fi
if [ "$VERDICT" = APPROVE ] && [ -z "$HOLD" ] && { [ "${PRR_DRY_RUN:-0}" != "1" ] || [ -n "${PRR_CI_FILE:-}" ]; }; then
  ci_fetch() {  # → $TMP/ci.json ; non-zero if GitHub could not be read
    [ -n "${PRR_CI_FILE:-}" ] && { cp "$PRR_CI_FILE" "$TMP/ci.json"; return 0; }
    gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100" --jq '.check_runs' > "$TMP/runs.json" 2>/dev/null || return 1
    gh api "repos/$REPO/commits/$SHA/status?per_page=100" --jq '.statuses' > "$TMP/statuses.json" 2>/dev/null || echo '[]' > "$TMP/statuses.json"
    python3 -c 'import json,sys; json.dump({"check_runs": json.load(open(sys.argv[1])), "statuses": json.load(open(sys.argv[2]))}, open(sys.argv[3], "w"))' \
      "$TMP/runs.json" "$TMP/statuses.json" "$TMP/ci.json"
  }
  WAIT="${PRR_CI_WAIT:-60}"; WAITED=0
  while :; do
    if ci_fetch; then CI_OUT="$(python3 "$HERE/ci-state.py" "$TMP/ci.json" 2>/dev/null)"; else CI_OUT="CI_STATE=unknown"; fi
    CI_STATE="$(echo "$CI_OUT" | sed -n 's/^CI_STATE=//p')"; CI_STATE="${CI_STATE:-unknown}"
    [ "$CI_STATE" = pending ] && [ "$WAITED" -lt "$WAIT" ] || break
    sleep 15; WAITED=$((WAITED + 15))
  done
  CI_FAILED="$(echo "$CI_OUT" | sed -n 's/^CI_FAILED=//p')"; CI_PENDING="$(echo "$CI_OUT" | sed -n 's/^CI_PENDING=//p')"
  case "$CI_STATE" in
    failure) HOLD="ci"
             NOTE="⏸️ **Not approving yet — CI is failing on this commit:** ${CI_FAILED}. The code review below found no blockers. Push a fix, or re-run CI and comment \`/maestro review\` when it is green." ;;
    pending) NOTE="⏳ CI was still running when I posted this (${CI_PENDING}) — the approve covers the code, not the checks." ;;
    unknown) NOTE="⚠️ I could not read the CI status of this commit — the approve covers the code, not the checks." ;;
  esac
fi

build() {  # $1 = inline|folded
  python3 - "$1" "$SHA" "$VERDICT" "$SHADOW" "$BODY_FILE" "${COMMENTS:-}" "$HOLD" "$NOTE" "$CI_STATE" > "$TMP/payload.json" <<'PY'
import json, sys
mode, sha, verdict, shadow, body_file, comments_file, hold, note, ci = sys.argv[1:10]
body = open(body_file).read().rstrip()
comments = json.load(open(comments_file)) if comments_file else []
event = "COMMENT" if (verdict == "UNREVIEWED" or hold) else verdict
if note and hold:
    body = f"> {note}\n\n{body}"
elif note:
    body = f"{body}\n\n> {note}"
if shadow == "1":
    event = "COMMENT"
    body = f"> 🫥 **Shadow mode** — would have been `{verdict}`; not counted as a review.\n\n{body}"
if mode == "folded" and comments:
    body += "\n\n---\n" + "\n".join(f"- `{c['path']}:{c['line']}` — {c['body']}" for c in comments)
    comments = []
extra = (f" held={hold}" if hold else "") + (f" ci={ci}" if ci not in ("skipped", "") else "")
body += f"\n\n<!-- maestro-pr-review sha={sha} verdict={verdict}{extra} -->"
payload = {"commit_id": sha, "event": event, "body": body}
if comments:
    payload["comments"] = [{"path": c["path"], "line": int(c["line"]), "side": "RIGHT", "body": c["body"]}
                           for c in comments]
print(json.dumps(payload))
PY
}

build inline || { echo "ERROR=cannot build payload"; exit 1; }
if [ "${PRR_DRY_RUN:-0}" = "1" ]; then cat "$TMP/payload.json"; echo; exit 0; fi

if gh api "repos/$REPO/pulls/$PR/reviews" --method POST --input "$TMP/payload.json" > "$TMP/resp.json" 2> "$TMP/err.txt"; then
  :
elif [ -n "$COMMENTS" ] && grep -qiE '422|line|position|pull_request_review_thread' "$TMP/err.txt"; then
  echo "WARN=inline comments rejected, retrying folded into body"
  build folded && gh api "repos/$REPO/pulls/$PR/reviews" --method POST --input "$TMP/payload.json" > "$TMP/resp.json" \
    || { echo "ERROR=review post failed"; cat "$TMP/err.txt"; exit 1; }
else
  echo "ERROR=review post failed"; cat "$TMP/err.txt"; exit 1
fi

echo "CI_STATE=$CI_STATE"
[ -z "$HOLD" ] || echo "APPROVE_HELD=$HOLD"
python3 - "$TMP/resp.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
print(f"REVIEW_ID={r.get('id')}\nREVIEW_STATE={r.get('state')}\nREVIEW_URL={r.get('html_url')}")
PY
