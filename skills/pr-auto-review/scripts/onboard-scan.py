#!/usr/bin/env python3
"""onboard-scan.py — draft a review profile for a repo from its file tree.

Usage: onboard-scan.py <repo-name> <default-branch> <tree-paths.txt> <root-AGENTS.md|-> <out-dir>

Pure (no network): onboard-repo.sh fetches the inputs. Writes into <out-dir>:

  profile.json   complete and valid — stacks detected from the tree (globs = the
                 top-level directories where each stack's files live) and the
                 generic risk paths that match at least one real file
  review.md      the template, still carrying its {{placeholders}}
  ONBOARDING.md  what a person (or Claude) must still write, with the repo's own
                 rules / integration sections quoted as source material, and the
                 repos it names that are candidates for relations.json edges

validate-registry.py refuses a profile while review.md has placeholders or
ONBOARDING.md exists, so a half-onboarded repo cannot be merged by accident.
Prints ONBOARD_STACKS / ONBOARD_RISK_PATHS / ONBOARD_CONTEXT_NODES / ONBOARD_RELATED.
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _profiles import DEFAULT_RISK, DEFAULT_STACKS, REPOS, matches  # noqa: E402

_spec = importlib.util.spec_from_file_location("ctx", os.path.join(HERE, "context-assemble.py"))
ctx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctx)

IGNORED = re.compile(r"(^|/)(node_modules|build|dist|\.dart_tool|vendor|Pods|\.venv|__pycache__)/")


def detect_stacks(tree):
    """{stack: [globs]} — one glob per top-level entry holding that stack's files."""
    out = {}
    for stack, globs in DEFAULT_STACKS.items():
        hits = [p for p in tree if matches(p, globs)]
        if not hits:
            continue
        tops = sorted({p.split("/")[0] + ("/**" if "/" in p else "") for p in hits})
        out[stack] = tops
    return out


def detect_risk(tree):
    return [{"glob": r["glob"], "why": r["why"]} for r in DEFAULT_RISK if any(matches(p, [r["glob"]]) for p in tree)]


def related_repos(agents_text, repo, owner_prefix="carespace-"):
    names = set(re.findall(rf"\b{re.escape(owner_prefix)}[a-z0-9-]+\b", agents_text or ""))
    return sorted(names - {repo})


def build(repo, branch, tree, agents_text):
    tree = [p for p in tree if not IGNORED.search(p)]
    profile = {"repo": repo, "default_branch": branch, "stacks": detect_stacks(tree),
               "risk_paths": detect_risk(tree),
               "human_paths": [".github/workflows/**"], "ci_ignore": ""}
    nodes = sum(1 for p in tree if os.path.basename(p) == "AGENTS.md")
    related = related_repos(agents_text, repo)
    source = "\n".join(ctx.priority_sections(agents_text)) if agents_text else ""
    notes = [f"# Onboarding {repo} — delete this file when done\n",
             "`profile.json` was generated from the file tree and is valid as it stands; "
             "tighten it. `review.md` is the empty template. `validate-registry.py` fails "
             "until `review.md` has no `{{placeholders}}` and this file is gone.\n",
             "## To do\n",
             "- [ ] `profile.json` › `stacks`: globs are whole top-level directories — narrow them if a "
             "directory mixes stacks; add a stack that detection missed"
             + ("" if profile["stacks"] else " (**none was detected** — add at least one)") + ".",
             "- [ ] `profile.json` › `risk_paths`: add this repo's own (auth, persistence of PHI, public "
             "contracts, deploy config). Every glob must match real files.",
             "- [ ] `review.md` › **What breaks here**: 5–8 concrete ways a PR breaks this repo, from the "
             "rules quoted below. Cite the rule; name the path.",
             "- [ ] `review.md` › **Not a blocker here**: what CI, rulesets or the design already cover.",
             "- [ ] `../../relations.json`: one edge per contract with "
             + (", ".join(f"`{r}`" for r in related) if related else "other repos (none named in AGENTS.md)")
             + ". Verify the paths on **both** sides.",
             "- [ ] Dry-run against 3–5 merged PRs (REFERENCE.md › Run locally) and read what would have been posted.\n"]
    if nodes == 0:
        notes.append("> ⚠️ **No Context Layer** (`AGENTS.md`) in this repo. Run the `context-layer` skill on it "
                     "first — without it the reviewer has only the diff and this profile.\n")
    notes.append("## Source material — rules and integration sections of the root AGENTS.md\n")
    notes.append(source if source else "_Nothing to quote: no root AGENTS.md, or it has no rules / "
                                       "integration / invariants sections._")
    return profile, "\n".join(notes) + "\n", nodes, related


if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    repo, branch, tree_file, agents_file, out = sys.argv[1].split("/")[-1], *sys.argv[2:6]
    with open(tree_file) as fh:
        tree = [l.strip() for l in fh if l.strip()]
    agents = ""
    if agents_file != "-" and os.path.isfile(agents_file):
        with open(agents_file, encoding="utf-8", errors="replace") as fh:
            agents = fh.read()
    profile, notes, nodes, related = build(repo, branch, tree, agents)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "profile.json"), "w") as fh:
        json.dump(profile, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(REPOS, "_template", "review.md")) as src, open(os.path.join(out, "review.md"), "w") as dst:
        dst.write(src.read())
    with open(os.path.join(out, "ONBOARDING.md"), "w") as fh:
        fh.write(notes)
    print(f"ONBOARD_STACKS={','.join(profile['stacks'])}")
    print(f"ONBOARD_RISK_PATHS={len(profile['risk_paths'])}")
    print(f"ONBOARD_CONTEXT_NODES={nodes}")
    print(f"ONBOARD_RELATED={','.join(related)}")
