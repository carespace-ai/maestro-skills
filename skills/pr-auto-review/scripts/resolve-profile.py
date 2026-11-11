#!/usr/bin/env python3
"""resolve-profile.py — stage the review profile for one PR.

Usage: resolve-profile.py <repo-name> <changed-files.txt> <out-dir>

Picks what THIS PR needs from the registry and writes it where the skill reads it:

  <out-dir>/profile.md      the repo's review notes (repos/<repo>/review.md) + the
                            checklist of every stack the changed files belong to
  <out-dir>/risk-files.txt  changed files on a risk path, "<path>\\t<why>" — the
                            reviewer reads these in full, however large the diff
  <out-dir>/human-files.txt changed files on a `human_paths` glob — post-review.sh
                            never approves a PR that touches one; a person does

A repo without a profile still gets one: stacks guessed from the changed paths
and the generic risk paths. Prints PROFILE / STACKS / RISK_FILES / HUMAN_FILES /
CI_IGNORE.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiles import DEFAULT_HUMAN, DEFAULT_RISK, DEFAULT_STACKS, REPOS, STACKS, load_profile, matches  # noqa: E402


def resolve(repo, changed):
    profile = load_profile(repo)
    stacks = (profile or {}).get("stacks") or DEFAULT_STACKS
    risk = (profile or {}).get("risk_paths")
    if risk is None:
        risk = DEFAULT_RISK
    used = [s for s, globs in stacks.items() if any(matches(f, globs) for f in changed)]
    risky = []
    for f in changed:
        why = next((r["why"] for r in risk if matches(f, [r["glob"]])), None)
        if why:
            risky.append((f, why))
    human_globs = (profile or {}).get("human_paths")
    if human_globs is None:
        human_globs = DEFAULT_HUMAN
    human = [f for f in changed if matches(f, human_globs)]
    return profile, used, risky, human


def render(repo, profile, used, risky):
    parts = [f"# Review profile — {repo}\n"]
    notes = os.path.join(REPOS, repo, "review.md")
    if profile and os.path.isfile(notes):
        with open(notes) as fh:
            parts.append(fh.read().strip() + "\n")
    else:
        parts.append("_This repo has no review profile yet — generic checklists only "
                     "(onboard it: `repos/README.md`)._\n")
    if risky:
        parts.append("## Risk files in this PR — read each one in full\n\n"
                     + "\n".join(f"- `{f}` — {why}" for f, why in risky) + "\n")
    for s in used:
        path = os.path.join(STACKS, f"{s}.md")
        if os.path.isfile(path):
            with open(path) as fh:
                parts.append(fh.read().strip() + "\n")
    return "\n".join(parts)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    repo, files, out = sys.argv[1].split("/")[-1], sys.argv[2], sys.argv[3]
    with open(files) as fh:
        changed = [l.strip() for l in fh if l.strip()]
    profile, used, risky, human = resolve(repo, changed)
    with open(os.path.join(out, "profile.md"), "w") as fh:
        fh.write(render(repo, profile, used, risky))
    with open(os.path.join(out, "risk-files.txt"), "w") as fh:
        fh.write("".join(f"{f}\t{why}\n" for f, why in risky))
    print(f"PROFILE={repo if profile else 'default'}")
    print(f"STACKS={','.join(used)}")
    with open(os.path.join(out, "human-files.txt"), "w") as fh:
        fh.write("".join(f"{f}\n" for f in human))
    print(f"RISK_FILES={len(risky)}")
    print(f"HUMAN_FILES={len(human)}")
    print(f"CI_IGNORE={(profile or {}).get('ci_ignore') or ''}")
