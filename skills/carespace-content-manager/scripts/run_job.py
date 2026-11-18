#!/usr/bin/env python3
"""Run a content-manager job: python3 run_job.py <job-dir> [--env strapi-171]
   Bootstrap the jobs workspace: python3 run_job.py --init [--root PATH]

A job folder contains plan.json (+ optional records/). State lands in
state.json after EVERY write, so re-running resumes. See templates/ for
per-kind plan examples and references/recipes.md for the contracts.
"""
import argparse, json, os, subprocess, sys
import mcp_client
from runners import (
    compose_program, compose_survey, compose_calendar, publish_chain, scan_fill,
    restore_snapshot,
)
from runners.common import Job

KINDS = {
    "compose-program": compose_program, "compose-survey": compose_survey,
    "compose-calendar": compose_calendar, "publish-chain": publish_chain,
    "scan-fill": scan_fill, "restore-snapshot": restore_snapshot,
}

CLAUDE_MD = """# Carespace content jobs — workspace map

One folder per job: `YYYY-MM-DD-<topic>/` containing `brief.md` (the physio-readable
spec + approval), `plan.json` (runner input), `records/` (per-record payloads,
`<carespaceId>.json`), `state.json` (resume point — never hand-edit), `log.txt`.

## Routing table (task -> template -> runner kind)
| Task | Template | kind |
|---|---|---|
| Build a program from exercises | templates/compose-program.json | compose-program |
| Author a survey | templates/compose-survey.json | compose-survey |
| Build a calendar template | templates/compose-calendar.json | compose-calendar |
| Publish a reviewed draft tree | templates/publish-chain.json | publish-chain |
| Fill a batch of exercises | templates/scan-fill.json | scan-fill |
| Restore authored content from a snapshot | templates/restore-snapshot.json | restore-snapshot |

Templates live in the carespace-content-manager skill's `templates/` directory.
Run: `python3 <skill>/scripts/run_job.py <job-dir>`. Re-running resumes.
Read PROGRESS.md at session start; update it at session end.
"""

PROGRESS_MD = """# Progress

## Current state
(nothing yet)

## Last session
(nothing yet)

## Decisions
(none yet)

## Open questions
(none yet)
"""

def init_workspace(root):
    os.makedirs(root, exist_ok=True)
    if not os.path.isdir(os.path.join(root, ".git")):
        subprocess.run(["git", "init", "-q"], cwd=root, check=False)
    for name, content in (("CLAUDE.md", CLAUDE_MD), ("PROGRESS.md", PROGRESS_MD)):
        path = os.path.join(root, name)
        if not os.path.exists(path):
            with open(path, "w") as fh:
                fh.write(content)
    return root

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("job_dir", nargs="?")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--root", default=os.environ.get("CARESPACE_JOBS_ROOT",
                    os.path.expanduser("~/carespace-content-jobs")))
    ap.add_argument("--env")
    ap.add_argument("--claude-json")
    a = ap.parse_args(argv)
    if a.init:
        init_workspace(a.root)
        print(json.dumps({"initialized": a.root}))
        return 0
    if not a.job_dir:
        ap.error("job_dir required (or --init)")
    try:
        job = Job(a.job_dir)
    except (OSError, ValueError) as e:
        print(f"cannot load job: {e}", file=sys.stderr)
        return 1
    kind = job.plan.get("kind")
    mod = KINDS.get(kind)
    if not mod:
        print(f"unknown kind '{kind}' — one of {sorted(KINDS)}", file=sys.stderr)
        return 1
    problems = mod.validate(job.plan, job.records)
    if problems:
        for p in problems:
            print(f"PLAN INVALID: {p}", file=sys.stderr)
        return 1
    # env may be absent: a plugin-only install has no named registration, and
    # resolve_registration falls back to the plugin's stored admin token. It
    # raises with actionable guidance when neither source is configured.
    env = a.env or job.plan.get("env")
    try:
        reg = mcp_client.resolve_registration(env, path=a.claude_json)
    except mcp_client.RegistrationError as e:
        print(str(e), file=sys.stderr)
        return 1
    client = mcp_client.McpClient(reg["url"], reg["auth"])
    try:
        rc = mod.run(job, client)
        return rc or 0
    except Exception as e:
        job.log(f"FAILED: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
