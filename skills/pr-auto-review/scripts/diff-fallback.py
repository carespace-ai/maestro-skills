#!/usr/bin/env python3
"""diff-fallback.py — rebuild a readable diff when `gh pr diff` cannot serve one.

GitHub refuses the whole-PR diff above ~20k lines / 300 files, but the files API
still returns a per-file `patch`. This stitches those patches into diff.patch and
reports honestly what could not be read, so an unreadable PR is never approved
as if it had been reviewed.

Usage: diff-fallback.py <files.json> <diff.patch> <unread.txt> [changed-files-count]
       diff-fallback.py --names <files.json>      (just print the changed paths)
       diff-fallback.py --only <files.txt> <in.diff> <out.diff>
                                                  (keep only the file sections of a
                                                  unified diff whose path is listed)

  files.json   output of `gh api --paginate repos/R/pulls/N/files` (one array,
               several concatenated arrays, or one object per line — all accepted)
  diff.patch   written from the per-file patches
  unread.txt   text files whose patch GitHub omitted (too large), one per line

Prints DIFF_STATUS=ok|partial|missing and DIFF_UNREAD=<n>:
  ok       every changed text file has its patch
  partial  some text files have no patch — the reviewer must read them at HEAD
  missing  nothing readable at all — the PR cannot be reviewed
"""
import json
import re
import sys


def load(path):
    """Parse one or many concatenated JSON documents into a flat list of file objects."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    dec, i, files = json.JSONDecoder(), 0, []
    while i < len(raw):
        while i < len(raw) and raw[i].isspace():
            i += 1
        if i >= len(raw):
            break
        doc, i = dec.raw_decode(raw, i)
        files.extend(doc if isinstance(doc, list) else [doc])
    return [f for f in files if isinstance(f, dict) and f.get("filename")]


def build(files):
    chunks, unread = [], []
    for f in files:
        name, patch = f["filename"], f.get("patch")
        if patch:
            old = f.get("previous_filename") or name
            chunks.append(f"diff --git a/{old} b/{name}\n--- a/{old}\n+++ b/{name}\n{patch}\n")
        elif (f.get("changes") or 0) > 0:
            unread.append(name)           # text change GitHub would not inline
        # changes == 0 with no patch → binary / pure rename: nothing to read
    return "".join(chunks), unread


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--names":
        try:
            print("\n".join(f["filename"] for f in load(sys.argv[2])))
        except Exception:
            pass
        sys.exit(0)
    if len(sys.argv) == 5 and sys.argv[1] == "--only":
        with open(sys.argv[2]) as fh:
            keep = {l.strip() for l in fh if l.strip()}
        with open(sys.argv[3], encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        out = []
        for part in re.split(r"(?m)^(?=diff --git )", raw):
            m = re.match(r"diff --git a/(.*?) b/(.*)\n", part)
            if m and (m.group(1) in keep or m.group(2) in keep):
                out.append(part)
        with open(sys.argv[4], "w", encoding="utf-8") as fh:
            fh.write("".join(out))
        sys.exit(0)
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    try:
        files = load(sys.argv[1])
    except Exception:
        files = []
    expected = int(sys.argv[4]) if len(sys.argv) == 5 and sys.argv[4].isdigit() else len(files)
    diff, unread = build(files)
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        fh.write(diff)
    with open(sys.argv[3], "w", encoding="utf-8") as fh:
        fh.write("".join(f"{u}\n" for u in unread))
    listed_short = expected > len(files)   # files API caps at 3000 entries
    if not diff and (unread or expected > 0):
        status = "missing"
    elif unread or listed_short:
        status = "partial"
    else:
        status = "ok"
    print(f"DIFF_STATUS={status}\nDIFF_UNREAD={len(unread) + max(0, expected - len(files))}")
