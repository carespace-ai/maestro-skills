#!/usr/bin/env python3
"""ci-state.py — summarise CI for one commit from GitHub's check data.

Usage: ci-state.py <ci.json>

  ci.json  {"check_runs": [...], "statuses": [...]}
           check_runs = `GET /repos/R/commits/SHA/check-runs` .check_runs
           statuses   = `GET /repos/R/commits/SHA/status`     .statuses

Prints:
  CI_STATE=success|failure|pending|none
  CI_FAILED=<comma-separated names>     (failure)
  CI_PENDING=<comma-separated names>    (pending)

A check whose name matches the regex in PRR_CI_IGNORE is left out entirely
(preview deploys, flaky advisory jobs). Skipped / neutral / cancelled runs are
neither a failure nor pending: a cancelled run was superseded, not red.
"""
import json
import os
import re
import sys

FAILED = {"failure", "timed_out", "startup_failure", "action_required"}


def summarise(data, ignore=None):
    failed, pending, passed = [], [], 0
    skip = re.compile(ignore, re.I) if ignore else None

    def keep(name):
        return not (skip and skip.search(name))

    for r in data.get("check_runs") or []:
        name = r.get("name") or "?"
        if not keep(name):
            continue
        if r.get("status") != "completed":
            pending.append(name)
        elif r.get("conclusion") in FAILED:
            failed.append(name)
        elif r.get("conclusion") == "success":
            passed += 1
    for s in data.get("statuses") or []:
        name = s.get("context") or "?"
        if not keep(name):
            continue
        state = s.get("state")
        if state in ("failure", "error"):
            failed.append(name)
        elif state == "pending":
            pending.append(name)
        elif state == "success":
            passed += 1

    def uniq(xs):
        return sorted(set(xs))

    if failed:
        return "failure", uniq(failed), uniq(pending)
    if pending:
        return "pending", [], uniq(pending)
    return ("success" if passed else "none"), [], []


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1]) as fh:
        state, failed, pending = summarise(json.load(fh), os.environ.get("PRR_CI_IGNORE"))
    print(f"CI_STATE={state}")
    if failed:
        print("CI_FAILED=" + ", ".join(failed))
    if pending:
        print("CI_PENDING=" + ", ".join(pending))
