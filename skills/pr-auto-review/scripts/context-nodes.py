#!/usr/bin/env python3
"""context-nodes.py — pick which Context Layer nodes to load for a PR.

Usage: context-nodes.py <changed-files.txt> <tree-paths.txt>

  changed-files.txt  one changed path per line (from the PR)
  tree-paths.txt     every blob path in the repo at the BASE sha (git tree)

Prints node paths (AGENTS.md, or CLAUDE.md where a dir has no AGENTS.md) in
priority order, one per line. The caller loads them in that order and stops at
its token budget, so the order is the contract:

  1. the root node (repo architecture, integration rules, boundaries)
  2. the NEAREST node above each changed file, most-touched first
  3. the remaining intermediate ancestors, shallow → deep
"""
import os
import sys
from collections import Counter


def node_dirs(tree_paths):
    agents, claude = set(), set()
    for p in tree_paths:
        d, name = os.path.split(p)
        if name == "AGENTS.md":
            agents.add(d)
        elif name == "CLAUDE.md":
            claude.add(d)
    # CLAUDE.md is usually a symlink to AGENTS.md — only use it where AGENTS.md is missing
    nodes = {d: f"{d}/AGENTS.md" if d else "AGENTS.md" for d in agents}
    for d in claude - agents:
        nodes[d] = f"{d}/CLAUDE.md" if d else "CLAUDE.md"
    return nodes


def ancestors(path):
    """'' (root) first, then each parent dir down to the file's own dir."""
    parts = path.split("/")[:-1]
    return [""] + ["/".join(parts[: i + 1]) for i in range(len(parts))]


def select(changed, tree_paths):
    nodes = node_dirs(tree_paths)
    order, seen = [], set()

    def add(d):
        if d in nodes and d not in seen:
            seen.add(d)
            order.append(nodes[d])

    add("")
    nearest = Counter()
    for f in changed:
        hits = [d for d in ancestors(f) if d in nodes and d != ""]
        if hits:
            nearest[hits[-1]] += 1
    for d, _ in sorted(nearest.items(), key=lambda kv: (-kv[1], kv[0])):
        add(d)
    rest = {d for f in changed for d in ancestors(f) if d in nodes}
    for d in sorted(rest, key=lambda d: (d.count("/"), d)):
        add(d)
    return order


def read_lines(path):
    with open(path) as fh:
        return [l.strip() for l in fh if l.strip()]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    for n in select(read_lines(sys.argv[1]), read_lines(sys.argv[2])):
        print(n)
