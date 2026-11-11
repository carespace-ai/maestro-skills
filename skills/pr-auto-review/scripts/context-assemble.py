#!/usr/bin/env python3
"""context-assemble.py — build context-layer.md from the staged Context Layer nodes.

Usage: context-assemble.py <manifest.tsv> <out.md> <base-sha>

  manifest.tsv  one line per staged node, in priority order (context-nodes.py):
                <node path in the repo> TAB <local file holding its full text>

Every node is represented — none is silently dropped:

  root node    inlined in full up to PRR_ROOT_CAP chars. A longer root keeps its
               head, then the sections a reviewer needs most (integration rules,
               contracts, boundaries, invariants, hard rules) wherever they sit.
  other nodes  inlined in full while they fit PRR_CONTEXT_BUDGET chars in total;
               a node that does not fit is EXCERPTED: its priority sections (up to
               PRR_NODE_EXCERPT chars) plus its heading outline and the staged
               file path, so the reviewer can open the rest.

Prints CONTEXT_NODES / CONTEXT_NODES_EXCERPTED / CONTEXT_CHARS.
"""
import os
import re
import sys

ROOT_CAP = int(os.environ.get("PRR_ROOT_CAP", "60000"))
BUDGET = int(os.environ.get("PRR_CONTEXT_BUDGET", "60000"))
EXCERPT = int(os.environ.get("PRR_NODE_EXCERPT", "8000"))

PRIORITY = re.compile(
    r"integration|contract|boundar|invariant|hard rules?|app integration|"
    r"dependency direction|phi|hipaa|security", re.I)
HEADING = re.compile(r"^(#{1,4})\s+(.*\S)\s*$")


def sections(text):
    """Split markdown into (level, title, body) — body includes the heading line.
    Text before the first heading is a level-0 section titled ''."""
    out, level, title, buf, fenced = [], 0, "", [], False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        m = None if fenced else HEADING.match(line)
        if m:
            if buf:
                out.append((level, title, "".join(buf)))
            level, title, buf = len(m.group(1)), m.group(2), [line]
        else:
            buf.append(line)
    if buf:
        out.append((level, title, "".join(buf)))
    return out


def priority_sections(text):
    """Bodies of priority sections, each with its nested subsections."""
    secs, picked, i = sections(text), [], 0
    while i < len(secs):
        level, title, body = secs[i]
        if level and PRIORITY.search(title):
            j = i + 1
            while j < len(secs) and secs[j][0] > level:
                body += secs[j][2]
                j += 1
            picked.append(body)
            i = j
        else:
            i += 1
    return picked


def take(chunks, cap):
    """Concatenate chunks up to cap chars; the chunk that overflows is cut at a line."""
    out, used = [], 0
    for c in chunks:
        room = cap - used
        if room <= 0:
            break
        if len(c) > room:
            c = c[:room].rsplit("\n", 1)[0] + "\n…\n"
        out.append(c)
        used += len(c)
    return "".join(out)


def outline(text):
    return "\n".join(f"{'  ' * (lvl - 1)}- {title}" for lvl, title, _ in sections(text) if lvl)


def render_root(path, text, staged):
    if len(text) <= ROOT_CAP:
        return text, False
    head_cap = ROOT_CAP // 2
    head = text[:head_cap].rsplit("\n", 1)[0]
    tail = [s for s in priority_sections(text) if s not in head]
    body = (f"{head}\n\n> ⚠️ `{path}` is {len(text)} chars — the middle is omitted here. "
            f"Priority sections follow; the full file is staged at `{staged}`.\n\n"
            f"{take(tail, ROOT_CAP - head_cap)}\n\n**Full outline of `{path}`:**\n{outline(text)}\n")
    return body, True


def render_excerpt(path, text, staged):
    return (f"> ⚠️ EXCERPT — `{path}` is {len(text)} chars and did not fit. Priority sections "
            f"only; open `{staged}` for anything else the diff makes relevant.\n\n"
            f"{take(priority_sections(text), EXCERPT)}\n\n**Outline of `{path}`:**\n{outline(text)}\n")


def assemble(manifest, base_sha):
    parts, full, excerpted, used = [], 0, 0, 0
    for idx, (path, staged) in enumerate(manifest):
        with open(staged, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        is_root = idx == 0 and "/" not in path
        if is_root:
            body, cut = render_root(path, text, staged)
        elif used + len(text) <= BUDGET:
            body, cut = text, False
            used += len(text)
        else:
            body, cut = render_excerpt(path, text, staged), True
        full, excerpted = full + (not cut), excerpted + cut
        parts.append(f"\n<!-- context-layer node: {path} (base {base_sha[:7]})"
                     f"{' — excerpt' if cut else ''} -->\n{body}\n")
    return "".join(parts), full, excerpted


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    with open(sys.argv[1]) as fh:
        rows = [l.rstrip("\n").split("\t") for l in fh if l.strip()]
    doc, n_full, n_excerpt = assemble([(r[0], r[1]) for r in rows if len(r) == 2], sys.argv[3])
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"CONTEXT_NODES={n_full}\nCONTEXT_NODES_EXCERPTED={n_excerpt}\nCONTEXT_CHARS={len(doc)}")
