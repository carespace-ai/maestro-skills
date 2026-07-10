#!/usr/bin/env bash
# should-run.sh — decide whether to regenerate the Context Layer for an inbound
# GitHub push webhook. Reads the push payload from $CLAUDEHUB_INPUT_KWARGS (JSON,
# set by Maestro from the webhook body). Prints KEY=VALUE lines the skill consumes,
# ending with DECISION=RUN or DECISION=SKIP (+ REASON). Exit code is always 0;
# the skill acts on DECISION, not the exit code.
#
# Parsing is done in python3 (always present in the Maestro image) — do NOT rely
# on jq, which may be absent. The loop guards below are safety-critical: never
# weaken them to a "RUN on parse failure" fallback.
set -uo pipefail

python3 - <<'PY'
import json, os, re, sys

payload_raw = os.environ.get("CLAUDEHUB_INPUT_KWARGS", "").strip()

def out(**kw):
    for k, v in kw.items():
        print(f"{k}={v}")

def skip(reason):
    out(DECISION="SKIP", REASON=reason)
    sys.exit(0)

if not payload_raw:
    skip("no CLAUDEHUB_INPUT_KWARGS (no webhook payload)")

try:
    p = json.loads(payload_raw)
except Exception as e:
    skip(f"payload is not valid JSON ({e})")

repo = (p.get("repository") or {})
repo_full = repo.get("full_name") or ""
default_branch = repo.get("default_branch") or ""
clone_url = repo.get("clone_url") or (f"https://github.com/{repo_full}.git" if repo_full else "")
ref = p.get("ref") or ""
sender = ((p.get("sender") or {}).get("login")) or ""
pusher = ((p.get("pusher") or {}).get("name")) or ""

out(REPO_FULL=repo_full, DEFAULT_BRANCH=default_branch, REF=ref,
    SENDER=sender, PUSHER=pusher, CLONE_URL=clone_url)

# Not a push event (e.g. GitHub sent a ping / non-push event to the same URL)
if not ref:
    skip("payload has no push ref (not a push event)")
if not default_branch:
    skip("payload has no repository.default_branch")

# Guard 1 — only act on pushes to the repo's default branch (master/main)
if ref != f"refs/heads/{default_branch}":
    skip(f"push not to default branch (ref={ref}, default={default_branch})")

# Guard 2 — ignore automation authors (loop guard: the layer's own merge/push)
who = f"{sender} {pusher}".lower()
if re.search(r"\[bot\]|context-layer|claudehub|maestro", who):
    skip(f"automation author (sender={sender}, pusher={pusher})")

# Guard 3 — docs-only push = the context layer's own merge landing → skip (loop guard)
changed = set()
for c in (p.get("commits") or []):
    for key in ("added", "modified", "removed"):
        for f in (c.get(key) or []):
            changed.add(f)
# also consider head_commit if commits[] is absent (squash merges sometimes)
hc = p.get("head_commit") or {}
for key in ("added", "modified", "removed"):
    for f in (hc.get(key) or []):
        changed.add(f)

DOC_RE = re.compile(r"(^|/)(AGENTS\.md|CLAUDE\.md)$|^\.claude/|(^|/)\.gitignore$")
if changed:
    nondoc = [f for f in changed if not DOC_RE.search(f)]
    if not nondoc:
        skip("docs-only push (only AGENTS.md/CLAUDE.md/.claude/.gitignore changed)")

out(DECISION="RUN", REASON=f"code change on default branch ({default_branch})")
PY
