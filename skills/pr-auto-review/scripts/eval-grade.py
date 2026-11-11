#!/usr/bin/env python3
"""Grade eval reviews against evals/cases.json.

Usage:
  eval-grade.py                      grade every case that has a payload.json
  eval-grade.py <case-id> [payload]  grade one case (payload defaults to its dir)
  eval-grade.py --check              validate cases.json only (CI)

A payload is what `post-review.sh` prints under PRR_DRY_RUN=1. The reviewer's own
verdict is read from the marker in the body, so an approve that a gate turned
into a comment (human path, CI) still counts as the approve it was.

Outcomes
  bug case      caught        blocked, and the review names the defect
                flagged       approved, but the review names the defect (heads-up)
                wrong-reason  blocked for something else — the defect went unseen
                missed        approved without a word about it
  control case  clean         approved
                false-block   blocked a PR with no known defect
  preexisting   noted         approved, and the review names the older defect
                clean         approved without mentioning it (acceptable)
                false-block   blocked the PR for a defect it did not introduce
  either        unreviewed    the diff could not be read
                no-payload    not run yet

Exit code: 0 when every graded case is caught / clean, 1 otherwise, 2 on bad input.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.environ.get("PRR_EVAL_CASES") or os.path.join(HERE, "..", "evals", "cases.json")
HOME = os.environ.get("PRR_EVAL_HOME") or os.path.expanduser("~/.prr/evals")
GOOD = {"caught", "clean", "noted"}


def load_cases():
    return json.load(open(CASES))["cases"]


def check(cases):
    """Problems in cases.json, as a list of strings."""
    errs, seen = [], set()
    for i, c in enumerate(cases):
        cid = c.get("id") or f"#{i}"
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(c.get("id", ""))):
            errs.append(f"{cid}: id must be lowercase letters, digits and dashes")
        if cid in seen:
            errs.append(f"{cid}: duplicate id")
        seen.add(cid)
        if c.get("kind") not in ("bug", "control", "preexisting"):
            errs.append(f"{cid}: kind must be bug, control or preexisting")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(c.get("repo", ""))):
            errs.append(f"{cid}: repo must be owner/name")
        elif not os.path.isdir(os.path.join(HERE, "..", "repos", c["repo"].split("/")[1])):
            errs.append(f"{cid}: no profile for {c['repo']} under repos/")
        if not isinstance(c.get("pr"), int):
            errs.append(f"{cid}: pr must be a number")
        for k in ("base_sha", "head_sha"):
            if not re.fullmatch(r"[0-9a-f]{40}", str(c.get(k, ""))):
                errs.append(f"{cid}: {k} must be a full 40-character commit")
        exp = c.get("expect") or {}
        want = "REQUEST_CHANGES" if c.get("kind") == "bug" else "APPROVE"
        if exp.get("verdict") != want:
            errs.append(f"{cid}: a {c.get('kind')} case expects {want}")
        if c.get("kind") in ("bug", "preexisting") and not exp.get("any_keywords"):
            errs.append(f"{cid}: a {c.get('kind')} case needs expect.any_keywords")
        if c.get("kind") == "bug":
            if not c.get("fixed_by"):
                errs.append(f"{cid}: a bug case needs fixed_by")
        for kw in exp.get("any_keywords", []):
            try:
                re.compile(kw)
            except re.error as e:
                errs.append(f"{cid}: bad keyword regex {kw!r} ({e})")
        if not c.get("truth"):
            errs.append(f"{cid}: truth is empty")
    return errs


def grade(case, payload):
    body = payload.get("body") or ""
    m = re.search(r"maestro-pr-review sha=[0-9a-f]+ verdict=(\w+)", body)
    verdict = m.group(1) if m else ""
    if verdict == "UNREVIEWED" or not verdict:
        return "unreviewed", verdict or "?"
    if case["kind"] == "control":
        return ("clean" if verdict == "APPROVE" else "false-block"), verdict
    text = body + "\n" + "\n".join(
        f"{c.get('path', '')} {c.get('body', '')}" for c in payload.get("comments") or [])
    named = any(re.search(kw, text, re.I) for kw in case["expect"]["any_keywords"])
    if case["kind"] == "preexisting":
        if verdict != "APPROVE":
            return "false-block", verdict
        return ("noted" if named else "clean"), verdict
    if verdict == "REQUEST_CHANGES":
        return ("caught" if named else "wrong-reason"), verdict
    return ("flagged" if named else "missed"), verdict


def main(argv):
    try:
        cases = load_cases()
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR=cannot read {CASES} ({e})")
        return 2
    errs = check(cases)
    if errs:
        print("\n".join(f"ERROR={e}" for e in errs))
        return 2
    if argv[:1] == ["--check"]:
        print(f"OK={len(cases)} cases")
        return 0
    if argv:
        cases = [c for c in cases if c["id"] == argv[0]]
        if not cases:
            print(f"ERROR=unknown case: {argv[0]}")
            return 2
    rows, bad = [], 0
    for c in cases:
        path = argv[1] if len(argv) > 1 else os.path.join(HOME, c["id"], "payload.json")
        try:
            outcome, verdict = grade(c, json.load(open(path)))
        except OSError:
            outcome, verdict = "no-payload", "-"
        except ValueError:
            outcome, verdict = "unreviewed", "?"
        if outcome not in GOOD and outcome != "no-payload":
            bad += 1
        rows.append((c["id"], c["kind"], verdict, outcome))
    w = max(len(r[0]) for r in rows)
    for cid, kind, verdict, outcome in rows:
        print(f"{cid:<{w}}  {kind:<11}  {verdict:<15}  {outcome}")
    ran = [r for r in rows if r[3] != "no-payload"]
    bugs = [r for r in ran if r[1] == "bug"]
    ctrl = [r for r in ran if r[1] in ("control", "preexisting")]
    print(f"SUMMARY bugs_caught={sum(r[3] == 'caught' for r in bugs)}/{len(bugs)} "
          f"bugs_flagged={sum(r[3] == 'flagged' for r in bugs)} "
          f"controls_clean={sum(r[3] in GOOD for r in ctrl)}/{len(ctrl)} "
          f"not_run={len(rows) - len(ran)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
