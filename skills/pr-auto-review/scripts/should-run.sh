#!/usr/bin/env bash
# should-run.sh — decide whether (and how) to review a PR for an inbound GitHub
# webhook. Reads the payload from $CLAUDEHUB_INPUT_KWARGS (JSON, set by Maestro
# from the webhook body merged over the trigger's default input_kwargs). Prints
# KEY=VALUE lines the skill consumes, ending with DECISION=RUN|SKIP (+ REASON).
# Exit code is always 0; the skill acts on DECISION, not the exit code.
#
# MODE (when DECISION=RUN):
#   full      — PR opened / reopened / ready_for_review → full review
#   recheck   — new push on a PR whose latest bot review is CHANGES_REQUESTED →
#               only verify the previous blockers were fixed
#   override  — a human asked to clear the block (`/maestro approve` comment or
#               `maestro:override` label) → dismiss the bot's blocking review
#
# The inbound token webhook carries no X-GitHub-Event header, so the event type
# is inferred from the payload shape. Parsing is python3 (always in the Maestro
# image) — do NOT rely on jq. The skip guards (release-please, bots, own PRs,
# duplicate deliveries) are what keep this skill from blocking or looping:
# never weaken them to a "RUN on parse failure" fallback.
#
# Test seams (no network): PRR_BOT_LOGIN, PRR_REVIEWS_FILE (JSON list of PR
# reviews), PRR_PERMISSION (commenter's repo permission).
set -uo pipefail

python3 - <<'PY'
import json, os, re, sys, urllib.request

def out(**kw):
    for k, v in kw.items():
        print(f"{k}={v}")

def skip(reason):
    out(DECISION="SKIP", REASON=reason)
    sys.exit(0)

def run(mode, reason):
    out(MODE=mode, DECISION="RUN", REASON=reason)
    sys.exit(0)

def gh_api(path):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    req = urllib.request.Request(
        f"https://api.github.com/{path.lstrip('/')}",
        headers={"Accept": "application/vnd.github+json",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

payload_raw = os.environ.get("CLAUDEHUB_INPUT_KWARGS", "").strip()
if not payload_raw:
    skip("no CLAUDEHUB_INPUT_KWARGS (no webhook payload)")
try:
    p = json.loads(payload_raw)
except Exception as e:
    skip(f"payload is not valid JSON ({e})")

repo_full = (p.get("repository") or {}).get("full_name") or ""
action = p.get("action") or ""
shadow = "1" if (p.get("prr_shadow") or os.environ.get("PRR_SHADOW") == "1") else "0"
out(REPO_FULL=repo_full, ACTION=action, SHADOW=shadow)
if not repo_full:
    skip("payload has no repository.full_name")

# Optional rollout allowlist from the trigger's default input_kwargs
allow = p.get("prr_repos") or []
if allow and repo_full not in allow and repo_full.split("/")[-1] not in allow:
    skip(f"repo not in prr_repos allowlist ({repo_full})")

# ── Event shape ──────────────────────────────────────────────────────────────
if "pull_request" in p:
    event, pr = "pull_request", p["pull_request"]
elif "comment" in p and "issue" in p:
    event, pr = "issue_comment", None
    if not (p["issue"].get("pull_request")):
        skip("comment is on an issue, not a PR")
else:
    skip("payload is neither a pull_request nor an issue_comment event")

try:
    bot = os.environ.get("PRR_BOT_LOGIN") or gh_api("user").get("login", "")
except Exception as e:
    skip(f"cannot resolve bot login via GitHub API ({e})")
out(BOT_LOGIN=bot)

def bot_reviews(number):
    f = os.environ.get("PRR_REVIEWS_FILE")
    if f:
        reviews = json.load(open(f))
    else:
        reviews = gh_api(f"repos/{repo_full}/pulls/{number}/reviews?per_page=100")
    return [r for r in reviews if (r.get("user") or {}).get("login", "").lower() == bot.lower()]

def latest_state(reviews):
    # COMMENTED reviews don't change the approval state; look at the last decisive one
    decisive = [r for r in reviews if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")]
    return decisive[-1]["state"] if decisive else ""

# ── Override via comment ─────────────────────────────────────────────────────
if event == "issue_comment":
    number = p["issue"].get("number")
    body = ((p.get("comment") or {}).get("body") or "").strip()
    commenter = ((p.get("comment") or {}).get("user") or {}).get("login", "")
    out(PR_NUMBER=number, COMMENTER=commenter)
    if action != "created" or not re.match(r"^/maestro\s+approve\b", body, re.I):
        skip("comment is not a /maestro approve command")
    if commenter.lower() == bot.lower():
        skip("comment authored by the bot itself")
    perm = os.environ.get("PRR_PERMISSION")
    if not perm:
        try:
            perm = gh_api(f"repos/{repo_full}/collaborators/{commenter}/permission").get("permission", "")
        except Exception as e:
            skip(f"cannot read commenter permission ({e})")
    if perm not in ("admin", "maintain", "write"):
        skip(f"commenter {commenter} lacks write access (permission={perm})")
    if latest_state(bot_reviews(number)) != "CHANGES_REQUESTED":
        skip("no active bot CHANGES_REQUESTED review to clear")
    out(OVERRIDE_BY=commenter)
    run("override", f"/maestro approve by {commenter}")

# ── pull_request events ──────────────────────────────────────────────────────
number = pr.get("number") or p.get("number")
head = pr.get("head") or {}
base = pr.get("base") or {}
author = (pr.get("user") or {}).get("login", "")
head_ref = head.get("ref", "")
head_sha = head.get("sha", "")
labels = [l.get("name", "") for l in (pr.get("labels") or [])]
out(PR_NUMBER=number, HEAD_SHA=head_sha, BASE_SHA=base.get("sha", ""),
    BASE_REF=base.get("ref", ""), HEAD_REF=head_ref, AUTHOR=author)

if pr.get("state") == "closed":
    skip("PR is closed")

# Override via label (labeling already requires triage+ access)
if action == "labeled":
    if (p.get("label") or {}).get("name") != "maestro:override":
        skip("label is not maestro:override")
    if latest_state(bot_reviews(number)) != "CHANGES_REQUESTED":
        skip("no active bot CHANGES_REQUESTED review to clear")
    sender = (p.get("sender") or {}).get("login", "")
    out(OVERRIDE_BY=sender)
    run("override", f"maestro:override label by {sender}")

if action not in ("opened", "reopened", "ready_for_review", "synchronize"):
    skip(f"action {action!r} is not reviewed")
if pr.get("draft"):
    skip("PR is a draft")

# Guard — release-please (any one signal is enough)
if (head_ref.startswith("release-please--")
        or any(l.startswith("autorelease:") for l in labels)
        or author.lower().startswith("release-please")):
    skip("release-please PR")

# Guard — automation authors: bots, dependency updaters, Maestro's own PRs
if author.lower() == bot.lower():
    skip("PR authored by the reviewing bot (GitHub forbids self-approval)")
if re.search(r"\[bot\]$|^dependabot|^renovate", author, re.I):
    skip(f"bot-authored PR ({author})")
if re.search(r"maestro|claudehub", author, re.I) or \
        re.match(r"^(claude/context-layer|pipeline/|bmad/)", head_ref):
    skip(f"Maestro automation PR (author={author}, head={head_ref})")

reviews = bot_reviews(number)
state = latest_state(reviews)
marker = f"maestro-pr-review sha={head_sha}"

# Idempotency — GitHub redeliveries and reopen-after-review
if any(marker in (r.get("body") or "") for r in reviews):
    skip("this head SHA was already reviewed (duplicate delivery)")

if action == "synchronize":
    if state != "CHANGES_REQUESTED":
        skip("new push, but the bot has no open CHANGES_REQUESTED (nothing to recheck)")
    run("recheck", "new push on a PR the bot blocked — verify previous blockers")

if state == "CHANGES_REQUESTED":
    run("recheck", f"{action} on a PR the bot blocked — verify previous blockers")
run("full", f"PR {action}")
PY
