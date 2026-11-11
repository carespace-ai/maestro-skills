#!/usr/bin/env python3
"""render-review.py — build the review body from templates/ and the reviewer's findings.

Usage: render-review.py <review.json> <VERDICT> <HEAD_SHA> <STAGE_DIR> <OUT_BODY.md> <OUT_COMMENTS.json>

The reviewer writes findings as JSON (shape: templates/review.example.json); this
script lays them out, so every review on GitHub has the same sections in the same
order whatever the model wrote. The footer (commit, scope, size, profile,
contracts) comes from the staged files, not from the reviewer.

Fields per verdict:
  APPROVE          summary, checked (1-8) required; blockers must be empty.
                   coverage required on a full review when the diff is > 1500
                   lines or DIFF_STATUS=partial.
  REQUEST_CHANGES  summary, blockers (>=1: title, path, when, fix; line, rule optional).
  UNREVIEWED       reason.
  Optional everywhere: cross_repo, heads_up, coverage, resolved.

Inline comments are generated from the blockers that carry a line number.
Exit 1 with ERROR=<what to fix> when the findings do not fit; nothing is written.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
FILES = {"APPROVE": "approve", "REQUEST_CHANGES": "request-changes", "UNREVIEWED": "unreviewed"}
BIG_DIFF = 1500


def die(msg):
    print(f"ERROR=review.json: {msg}")
    sys.exit(1)


def text(v):
    """One field as inline markdown: single paragraph, no HTML comments (the marker is ours)."""
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        return ""
    s = str(v).replace("<!--", "").replace("-->", "").replace("maestro-pr-review", "maestro pr review")
    return re.sub(r"\s*\n\s*", " ", s).strip()


def items(d, key):
    v = d.get(key)
    if v is None:
        return []
    if not isinstance(v, list):
        die(f"`{key}` must be a list")
    return v


def strings(d, key):
    return [t for t in (text(x) for x in items(d, key)) if t]


def code(s):
    return "`" + text(s).replace("`", "") + "`"


def count(path):
    try:
        with open(path, errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def main():
    if len(sys.argv) != 7:
        print(__doc__)
        sys.exit(2)
    src, verdict, sha, stage, out_body, out_comments = sys.argv[1:7]
    if verdict not in FILES:
        die(f"unknown verdict {verdict}")
    try:
        d = json.load(open(src))
    except (OSError, ValueError) as e:
        die(f"not readable JSON ({e})")
    if not isinstance(d, dict):
        die("must be a JSON object")
    try:
        st = dict(l.strip().split("=", 1) for l in open(os.path.join(stage, "status.env")) if "=" in l)
    except OSError:
        st = {}
    lines = count(os.path.join(stage, "diff.patch"))
    nfiles = count(os.path.join(stage, "files.txt"))
    scope = st.get("REVIEW_SCOPE", "full")
    mode = os.environ.get("MODE", "full")

    v = {}
    v["SUMMARY"] = text(d.get("summary"))
    v["REASON"] = text(d.get("reason"))

    checked = []
    for c in items(d, "checked"):
        if isinstance(c, dict) and text(c.get("area")) and text(c.get("result")):
            checked.append(f"- **{text(c['area'])}** — {text(c['result'])}")
        elif text(c):
            checked.append(f"- {text(c)}")
    v["CHECKED"] = "\n".join(checked)

    cross = []
    for c in items(d, "cross_repo"):
        if isinstance(c, dict) and text(c.get("repo")) and text(c.get("result")):
            cross.append(f"- {code(c['repo'])} — {text(c['result'])}")
        elif text(c):
            cross.append(f"- {text(c)}")
    v["CROSS_REPO"] = "\n".join(cross)
    v["HEADS_UP"] = "\n".join(f"- {s}" for s in strings(d, "heads_up"))
    v["RESOLVED"] = "\n".join(f"- ✅ {s}" for s in strings(d, "resolved"))

    cov = d.get("coverage") or {}
    if not isinstance(cov, dict):
        die("`coverage` must be an object with read / skimmed / not_read lists")
    cov_lines = [f"- **{label}:** {', '.join(strings(cov, key))}"
                 for key, label in (("read", "Read in full"), ("skimmed", "Skimmed"), ("not_read", "Not read"))
                 if strings(cov, key)]
    v["COVERAGE"] = "\n".join(cov_lines)

    blockers, comments = [], []
    for i, b in enumerate(items(d, "blockers"), 1):
        if not isinstance(b, dict):
            die(f"blocker {i} must be an object")
        miss = [k for k in ("title", "path", "when", "fix") if not text(b.get(k))]
        if miss:
            die(f"blocker {i} lacks {', '.join(miss)} — a blocker needs what breaks, where, when and the fix")
        line = b.get("line")
        line = line if isinstance(line, int) and not isinstance(line, bool) and line > 0 else None
        where = text(b["path"]).replace("`", "") + (f":{line}" if line else "")
        block = [f"#### {i}. {text(b['title'])}", f"- **Where:** `{where}`",
                 f"- **When:** {text(b['when'])}", f"- **Fix:** {text(b['fix'])}"]
        if text(b.get("rule")):
            block.append(f"- **Rule:** {text(b['rule'])}")
        blockers.append("\n".join(block))
        if line:
            comments.append({"path": text(b["path"]), "line": line,
                             "body": f"🛑 **{text(b['title'])}**\n\n**When:** {text(b['when'])}\n\n**Fix:** {text(b['fix'])}"})
    v["BLOCKERS"] = "\n\n".join(blockers)
    v["N"] = str(len(blockers))

    if verdict == "APPROVE":
        if blockers:
            die("an APPROVE cannot list blockers — pass REQUEST_CHANGES, or drop them")
        if not v["SUMMARY"]:
            die("`summary` is required")
        if not 1 <= len(checked) <= 8:
            die("`checked` needs 1 to 8 entries: the rules, contracts or risks this PR touches and what you found")
        partial = st.get("DIFF_STATUS") == "partial"
        if scope != "delta" and (partial or (lines or 0) > BIG_DIFF) and not v["COVERAGE"]:
            die("`coverage` is required on a large or partially staged diff: say what was read in full and what was skimmed")
    elif verdict == "REQUEST_CHANGES":
        if not v["SUMMARY"]:
            die("`summary` is required")
        if not blockers:
            die("REQUEST_CHANGES needs at least one blocker")
    elif not v["REASON"]:
        die("`reason` is required for UNREVIEWED")

    foot = [f"Reviewed at `{sha[:7]}`"]
    if verdict != "UNREVIEWED":
        if scope == "delta" and st.get("DELTA_BASE"):
            foot.append(f"changes since `{st['DELTA_BASE'][:7]}`")
        elif mode == "recheck":
            foot.append("re-check of the previous blockers + new changes")
        else:
            foot.append("full review")
    if nfiles is not None and lines is not None:
        foot.append(f"{nfiles} file(s), {lines} diff lines")
    if st.get("PROFILE"):
        foot.append(f"profile {code(st['PROFILE'])}")
    if st.get("RELATION_IDS"):
        foot.append("contracts: " + ", ".join(code(r) for r in st["RELATION_IDS"].split(",") if r.strip()))
    v["FOOTER"] = " · ".join(foot)

    tpl = open(os.path.join(TEMPLATES, FILES[verdict] + ".template.md")).read()
    tpl = re.sub(r"<!-- if:(\w+) -->\n(.*?)<!-- end:\1 -->\n",
                 lambda m: m.group(2) if v.get(m.group(1)) else "", tpl, flags=re.S)
    body = re.sub(r"\{\{(\w+)\}\}", lambda m: v.get(m.group(1), ""), tpl).strip() + "\n"
    with open(out_body, "w") as fh:
        fh.write(body)
    with open(out_comments, "w") as fh:
        json.dump(comments, fh)
    print(f"RENDERED={FILES[verdict]}")
    print(f"INLINE_COMMENTS={len(comments)}")


if __name__ == "__main__":
    main()
