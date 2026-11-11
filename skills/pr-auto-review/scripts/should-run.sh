#!/usr/bin/env bash
# should-run.sh — decide whether (and how) to review a PR for an inbound GitHub
# webhook. Reads the payload from $CLAUDEHUB_INPUT_KWARGS (JSON, set by Maestro
# from the webhook body merged over the trigger's default input_kwargs). Prints
# KEY=VALUE lines the skill consumes, ending with DECISION=RUN|SKIP (+ REASON).
# Exit code is always 0; the skill acts on DECISION, not the exit code.
#
# MODE (when DECISION=RUN):
#   full      — PR opened / reopened / ready_for_review, or a new push the bot
#               has no earlier clean read to build on → full review of the head
#   delta     — new push on a PR whose latest bot review found no blockers →
#               review only what changed since that commit (DELTA_BASE). The
#               reviewer falls back to a full review when that diff cannot be
#               built (force-push, rebase)
#   recheck   — new push on a PR whose latest bot review is CHANGES_REQUESTED →
#               only verify the previous blockers were fixed
#   (a new push after a human override — the bot's REQUEST_CHANGES review was
#   dismissed — is skipped. A dismissed APPROVE is not an override: that is
#   branch protection dropping a stale approval on push, and the new head still
#   needs its review.)
#   override  — a human asked to clear the block (`/maestro approve` comment or
#               `maestro:override` label) → dismiss the bot's blocking review
#
# A `/maestro review` comment (write access) asks for a fresh review of the
# current head even if that SHA was already reviewed — the way back after the
# bot held its approve for failing CI or an unreadable diff. It runs the same
# guards as a PR event and routes to full or recheck.
#
# The inbound token webhook carries no X-GitHub-Event header, so the event type
# is inferred from the payload shape. Parsing is python3 (always in the Maestro
# image) — do NOT rely on jq. The skip guards (release-please, bots, own PRs,
# duplicate deliveries) are what keep this skill from blocking or looping:
# never weaken them to a "RUN on parse failure" fallback.
#
# Every KEY=VALUE printed is also written, shell-quoted and exported, to
# $PRR_HOME/run-<payload hash>.env (default under ~/.prr) together with S (this
# scripts dir) and PRR_DIR (the staging dir); its path is printed as RUN_ENV.
# Shell variables do not survive between the skill's Bash calls, so every later
# step starts by sourcing that file. PR-controlled text (title, body, branch
# names) is never written to it.
#
# Test seams (no network): PRR_BOT_LOGIN, PRR_REVIEWS_FILE (JSON list of PR
# reviews), PRR_PERMISSION (commenter's repo permission), PRR_PR_FILE (the PR
# object fetched for a `/maestro review` comment).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_auth.sh"
export PRR_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 - <<'PY'
import hashlib, json, os, re, shlex, sys, urllib.request

ENV = {}

def out(**kw):
    for k, v in kw.items():
        print(f"{k}={v}")
        ENV[k] = str(v)

def finish():
    """Persist what the later steps need — they run in separate shells."""
    ENV["S"] = os.environ.get("PRR_SCRIPTS", "")
    if ENV.get("REPO_FULL") and ENV.get("PR_NUMBER"):
        ENV["PRR_DIR"] = os.environ.get("PRR_DIR") or \
            f"/tmp/prr-{ENV['REPO_FULL'].split('/')[-1]}-{ENV['PR_NUMBER']}"
    home = os.environ.get("PRR_HOME") or os.path.expanduser("~/.prr")
    try:
        os.makedirs(home, mode=0o700, exist_ok=True)
        key = hashlib.sha1(os.environ.get("CLAUDEHUB_INPUT_KWARGS", "").encode()).hexdigest()[:12]
        path = os.path.join(home, f"run-{key}.env")
        with open(path, "w") as fh:
            fh.write("".join(f"export {k}={shlex.quote(v)}\n" for k, v in ENV.items()
                             if re.fullmatch(r"[A-Z_][A-Z0-9_]*", k)))
        print(f"RUN_ENV={path}")
    except OSError as e:
        print(f"WARN=could not write the run env file ({e})")
    sys.exit(0)

def skip(reason):
    out(DECISION="SKIP", REASON=reason)
    finish()

def run(mode, reason):
    out(MODE=mode, DECISION="RUN", REASON=reason)
    finish()

def gh_api(path):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
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
    # COMMENTED reviews don't change the approval state; look at the last decisive one.
    # A DISMISSED review is a human override only when it was a block: GitHub also
    # turns the bot's own APPROVED into DISMISSED when "dismiss stale approvals on
    # push" is on, and that must not silence the bot. The marker in the body says
    # which it was.
    decisive = [r for r in reviews if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")]
    if not decisive:
        return ""
    last = decisive[-1]
    if last["state"] == "DISMISSED":
        return "OVERRIDDEN" if "verdict=REQUEST_CHANGES" in (last.get("body") or "") else "STALE"
    return last["state"]

def delta_base(reviews):
    """SHA the latest bot review read and found clean, or "" — what a new push is
    diffed against. Only the latest marked review counts, and never one whose
    approve was held because the diff could not be read."""
    for r in reversed(reviews):
        m = re.search(r"maestro-pr-review sha=([0-9a-f]{7,40}) verdict=(\w+)([^>]*?)-->", r.get("body") or "")
        if m:
            ok = m.group(2) == "APPROVE" and "held=unread" not in m.group(3)
            return m.group(1) if ok else ""
    return ""

def can_write(login):
    """(ok, permission) — whether `login` may override or re-trigger the bot."""
    perm = os.environ.get("PRR_PERMISSION")
    if not perm:
        try:
            perm = gh_api(f"repos/{repo_full}/collaborators/{login}/permission").get("permission", "")
        except Exception as e:
            skip(f"cannot read permission of {login} ({e})")
    return perm in ("admin", "maintain", "write"), perm

forced = False   # True for `/maestro review`: skip the same-SHA idempotency guard

# ── Override via comment ─────────────────────────────────────────────────────
if event == "issue_comment":
    number = p["issue"].get("number")
    body = ((p.get("comment") or {}).get("body") or "").strip()
    commenter = ((p.get("comment") or {}).get("user") or {}).get("login", "")
    out(PR_NUMBER=number, COMMENTER=commenter)
    m = re.match(r"^/maestro\s+(approve|review)\b", body, re.I) if action == "created" else None
    if not m:
        skip("comment is not a /maestro approve or /maestro review command")
    command = m.group(1).lower()
    if commenter.lower() == bot.lower():
        skip("comment authored by the bot itself")
    ok, perm = can_write(commenter)
    if not ok:
        skip(f"commenter {commenter} lacks write access (permission={perm})")
    if command == "approve":
        if latest_state(bot_reviews(number)) != "CHANGES_REQUESTED":
            skip("no active bot CHANGES_REQUESTED review to clear")
        out(OVERRIDE_BY=commenter)
        run("override", f"/maestro approve by {commenter}")
    # /maestro review — load the PR (a comment payload has no head/base) and fall
    # through to the pull_request guards below
    try:
        f = os.environ.get("PRR_PR_FILE")
        pr = json.load(open(f)) if f else gh_api(f"repos/{repo_full}/pulls/{number}")
    except Exception as e:
        skip(f"cannot read PR for /maestro review ({e})")
    action, forced = "rereview", True
    out(ACTION=action, REQUESTED_BY=commenter)

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

# Override via label — labeling only needs triage access, so hold it to the same
# bar as the comment: the person who added the label must have write access
if action == "labeled":
    if (p.get("label") or {}).get("name") != "maestro:override":
        skip("label is not maestro:override")
    if latest_state(bot_reviews(number)) != "CHANGES_REQUESTED":
        skip("no active bot CHANGES_REQUESTED review to clear")
    sender = (p.get("sender") or {}).get("login", "")
    ok, perm = can_write(sender) if sender else (False, "")
    if not ok:
        skip(f"{sender or 'unknown sender'} added maestro:override without write access (permission={perm})")
    out(OVERRIDE_BY=sender)
    run("override", f"maestro:override label by {sender}")

if action not in ("opened", "reopened", "ready_for_review", "synchronize", "rereview"):
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
if not forced and any(marker in (r.get("body") or "") for r in reviews):
    skip("this head SHA was already reviewed (duplicate delivery)")

if action == "synchronize":
    if state == "CHANGES_REQUESTED":
        run("recheck", "new push on a PR the bot blocked — verify previous blockers")
    if state == "OVERRIDDEN":
        skip("new push, but a human overrode the bot on this PR — stay out")
    # Branch protection dismisses stale approvals on push (state STALE), so every
    # new head needs a fresh review or the PR is stuck waiting for an approve again.
    # When the previous head was read and found clean, only the push is new.
    base = delta_base(reviews)
    if base and base != head_sha:
        out(DELTA_BASE=base)
        run("delta", f"new push — review what changed since {base[:7]}")
    run("full", "new push — re-review the new head")

if state == "CHANGES_REQUESTED":
    run("recheck", f"{action} on a PR the bot blocked — verify previous blockers")
run("full", f"PR {action}")
PY
