#!/usr/bin/env python3
"""validate-registry.py — check every repo profile against the template's contract.

Usage: validate-registry.py            (exit 1 and list problems if any profile is off)

Run by tests/test-profiles.sh, so a malformed profile fails before it is merged.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiles import REPOS, glob_re, load_profile, repo_names, stack_names  # noqa: E402

KEYS = {"repo", "default_branch", "stacks", "risk_paths", "ci_ignore"}
SECTIONS = ["## What breaks here", "## Not a blocker here"]


def check(repo, stacks):
    errs = []
    try:
        p = load_profile(repo)
    except Exception as e:
        return [f"profile.json is not valid JSON ({e})"]
    if p is None:
        return ["missing profile.json"]
    if p.get("repo") != repo:
        errs.append(f'"repo" is {p.get("repo")!r}, expected {repo!r} (must match the directory)')
    for k in sorted(set(p) - KEYS):
        errs.append(f"unknown key {k!r}")
    for k in ("default_branch", "stacks", "risk_paths"):
        if k not in p:
            errs.append(f"missing key {k!r}")
    if not isinstance(p.get("stacks"), dict) or not p.get("stacks"):
        errs.append('"stacks" must be a non-empty object {stack: [globs]}')
    else:
        for s, globs in p["stacks"].items():
            if s not in stacks:
                errs.append(f"stack {s!r} has no stacks/{s}.md (known: {', '.join(stacks)})")
            if not isinstance(globs, list) or not globs:
                errs.append(f"stack {s!r} needs a non-empty list of globs")
    for r in p.get("risk_paths") or []:
        if not isinstance(r, dict) or not r.get("glob") or not r.get("why"):
            errs.append(f'risk_paths entry needs "glob" and "why": {r!r}')
    for g in [g for gl in (p.get("stacks") or {}).values() if isinstance(gl, list) for g in gl] + \
             [r.get("glob", "") for r in p.get("risk_paths") or [] if isinstance(r, dict)]:
        try:
            glob_re(g)
        except re.error as e:
            errs.append(f"bad glob {g!r} ({e})")
    if p.get("ci_ignore"):
        try:
            re.compile(p["ci_ignore"])
        except re.error as e:
            errs.append(f'"ci_ignore" is not a valid regex ({e})')
    notes = os.path.join(REPOS, repo, "review.md")
    if not os.path.isfile(notes):
        errs.append("missing review.md")
    else:
        text = open(notes).read()
        for s in SECTIONS:
            if s not in text:
                errs.append(f"review.md lacks the section {s!r}")
        if "{{" in text:
            errs.append("review.md still has {{placeholders}} from the template")
    return errs


if __name__ == "__main__":
    stacks, bad = stack_names(), 0
    for repo in repo_names():
        for e in check(repo, stacks):
            print(f"{repo}: {e}")
            bad += 1
    print(f"REGISTRY_REPOS={len(repo_names())}\nREGISTRY_ERRORS={bad}")
    sys.exit(1 if bad else 0)
