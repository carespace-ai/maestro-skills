#!/usr/bin/env python3
"""resolve-relations.py — which cross-repo contracts does this PR touch?

Usage: resolve-relations.py <repo-name> <changed-files.txt> <out-dir>

Reads relations.json (edges provider → consumer). An edge is TRIGGERED when the
PR's repo is one end of it and a changed file lies on that end's paths:

  provider side  the PR changes a surface another repo consumes
  consumer side  the PR changes code that depends on another repo's surface

Writes:
  <out-dir>/relations.md   what to verify, per triggered edge (the reviewer reads it)
  <out-dir>/cross.tsv      "<edge id> TAB <other repo> TAB <glob>,<glob>…" — what
                           fetch-cross.sh must stage from the other repo

Prints RELATIONS=<n triggered> and RELATION_IDS=<ids>.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiles import ROOT, matches  # noqa: E402

RULES = {
    ("provider", "immediate"): (
        "`{other}` is deployed separately and meets this change the moment it ships. For every "
        "route, event, field, type or symbol this PR **removes, renames or re-types** on the "
        "surface, search the staged copy of `{other}` for its use. A use that would now fail on a "
        "normal path is a **blocker** — cite the consumer `file:line` next to the line in this "
        "diff. Purely additive changes (new optional field, new event the consumer ignores) are fine."),
    ("provider", "deferred"): (
        "`{other}` is pinned to a released version and only meets this change at its next bump, so "
        "nothing breaks today. If the PR removes, renames or re-types something `{other}` uses "
        "(check the staged copy), that is **one `⚠️ Heads-up` line** naming what the consumer must "
        "change at the bump — never a blocker."),
    ("consumer", "immediate"): (
        "This PR depends on `{other}`'s surface. For each route, field, event or symbol it starts "
        "to rely on, confirm it exists in the staged copy of `{other}` (its default branch). If it "
        "does not: check `linked-prs.md` for the `{other}` PR that adds it — then say the merge "
        "order in a `⚠️ Heads-up` (\"`{other}` first\"). It is a **blocker** only when no such PR "
        "exists and the missing piece is hit on a normal path."),
    ("consumer", "deferred"): (
        "This PR depends on a released version of `{other}`. Symbols it uses must exist at the "
        "**pinned** version, not on `{other}`'s default branch; a use of something not yet "
        "released does not build — CI shows it. Flag it only if CI cannot (a runtime-only contract)."),
}


def load_edges():
    with open(os.path.join(ROOT, "relations.json")) as fh:
        return json.load(fh).get("edges") or []


def triggered(repo, changed, edges):
    out = []
    for e in edges:
        for side, mine, other, theirs in (("provider", "provider_paths", e["consumer"], "consumer_paths"),
                                          ("consumer", "consumer_paths", e["provider"], "provider_paths")):
            if e[side] != repo:
                continue
            hits = [f for f in changed if matches(f, e[mine])]
            if hits:
                # what to stage from the other repo: a provider may name a compact
                # machine-readable contract (provider_stage) instead of all its sources
                stage = e.get("provider_stage") if side == "consumer" and e.get("provider_stage") else e[theirs]
                out.append({"edge": e, "side": side, "other": other, "hits": hits, "stage": stage})
    return out


def render(repo, items):
    if not items:
        return ""
    parts = [f"# Cross-repo contracts touched by this PR ({repo})\n",
             "Staged copies of the other repos are under `cross/<repo>/` (their default branch). "
             "`CROSS_<repo>=unavailable` in the fetch output means that copy could not be staged: "
             "do the check from this diff alone and add one `⚠️ Heads-up` line that the contract "
             "with that repo was **not verified** — never a blocker for that reason.\n"]
    for it in items:
        e, other = it["edge"], it["other"]
        role = "provides" if it["side"] == "provider" else "consumes"
        parts.append(
            f"## `{e['id']}` — this repo {role} · `{other}` is the {'consumer' if it['side'] == 'provider' else 'provider'} · {e['coupling']} coupling\n\n"
            f"**Surface:** {e['surface']}\n\n"
            f"**Changed here:** " + ", ".join(f"`{h}`" for h in it["hits"][:12])
            + (f" (+{len(it['hits']) - 12} more)" if len(it["hits"]) > 12 else "") + "\n\n"
            f"**Look in:** `cross/{other}/` — " + ", ".join(f"`{g}`" for g in it["stage"]) + "\n\n"
            f"**Check:** {RULES[(it['side'], e['coupling'])].format(other=other)}\n")
    return "\n".join(parts)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    repo, files, out = sys.argv[1].split("/")[-1], sys.argv[2], sys.argv[3]
    with open(files) as fh:
        changed = [l.strip() for l in fh if l.strip()]
    items = triggered(repo, changed, load_edges())
    with open(os.path.join(out, "relations.md"), "w") as fh:
        fh.write(render(repo, items))
    with open(os.path.join(out, "cross.tsv"), "w") as fh:
        fh.write("".join(f"{it['edge']['id']}\t{it['other']}\t{','.join(it['stage'])}\n" for it in items))
    print(f"RELATIONS={len(items)}")
    print("RELATION_IDS=" + ",".join(f"{it['edge']['id']}:{it['side']}" for it in items))
