#!/usr/bin/env bash
# post-review.sh — publish exactly ONE review on a PR.
#
# Usage: post-review.sh <REPO_FULL> <PR_NUMBER> <HEAD_SHA> <APPROVE|REQUEST_CHANGES> <BODY_FILE> [COMMENTS_JSON]
#
#   BODY_FILE      markdown review body written by the skill
#   COMMENTS_JSON  optional file: [{"path": "...", "line": 42, "body": "..."}] — blockers only,
#                  each anchored to a RIGHT-side line that exists in the diff
#
# Appends the hidden idempotency marker `<!-- maestro-pr-review sha=<HEAD_SHA> verdict=<V> -->`
# that should-run.sh uses to drop duplicate deliveries — never post a review without it.
# The review is pinned to HEAD_SHA (commit_id) so it can't land on a newer, unreviewed push.
#
# SHADOW=1 (or PRR_SHADOW=1) downgrades the event to COMMENT — shadow-mode rollout.
# PRR_DRY_RUN=1 prints the payload instead of calling GitHub (tests).
# If GitHub rejects the inline comments (422: line not in diff), retries once with the
# comments folded into the body, so a bad anchor never loses the review.
set -uo pipefail

REPO="${1:?REPO_FULL}"; PR="${2:?PR_NUMBER}"; SHA="${3:?HEAD_SHA}"
VERDICT="${4:?APPROVE|REQUEST_CHANGES}"; BODY_FILE="${5:?BODY_FILE}"; COMMENTS="${6:-}"
case "$VERDICT" in APPROVE|REQUEST_CHANGES) ;; *) echo "ERROR=invalid verdict $VERDICT"; exit 2 ;; esac
SHADOW="${SHADOW:-${PRR_SHADOW:-0}}"
TMP="$(mktemp -d)"

build() {  # $1 = inline|folded
  python3 - "$1" "$SHA" "$VERDICT" "$SHADOW" "$BODY_FILE" "${COMMENTS:-}" > "$TMP/payload.json" <<'PY'
import json, sys
mode, sha, verdict, shadow, body_file, comments_file = sys.argv[1:7]
body = open(body_file).read().rstrip()
comments = json.load(open(comments_file)) if comments_file else []
event = verdict
if shadow == "1":
    event = "COMMENT"
    body = f"> 🫥 **Shadow mode** — would have been `{verdict}`; not counted as a review.\n\n{body}"
if mode == "folded" and comments:
    body += "\n\n---\n" + "\n".join(f"- `{c['path']}:{c['line']}` — {c['body']}" for c in comments)
    comments = []
body += f"\n\n<!-- maestro-pr-review sha={sha} verdict={verdict} -->"
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

python3 - "$TMP/resp.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
print(f"REVIEW_ID={r.get('id')}\nREVIEW_STATE={r.get('state')}\nREVIEW_URL={r.get('html_url')}")
PY
