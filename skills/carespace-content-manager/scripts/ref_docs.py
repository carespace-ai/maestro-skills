#!/usr/bin/env python3
"""Read the clinical reference documents in ../reference-documents/ without
loading a whole file into the conversation. Stdlib only.

Every document is read as tables: an .xlsx gives one table per sheet, a .csv
one table, a .docx one table of paragraphs, and a .md/.txt one table of
sections (split on headings). Search and filter return only matching rows.

Usage:
  ref_docs.py list                          documents, their tables and row counts
  ref_docs.py schema <doc>                  columns per table, with the values of
                                            short categorical columns
  ref_docs.py search <doc|all> <term>...    rows containing ALL terms (case-insensitive)
        [--sheet S] [--cols A,B] [--limit N] [--max-chars N]
  ref_docs.py values <doc> --sheet S --col C   distinct values of one column, with counts
  ref_docs.py rows <doc> --sheet S --where Col=Value [--where ...]
        [--cols A,B] [--limit N] [--max-chars N]
                                            rows whose columns equal the values

<doc> is a file name in reference-documents/, with or without its extension,
or any unique part of it ("postural"). A sheet or column name may be any
unique case-insensitive prefix ("sag" = "Saggital View").
"""
import argparse, csv, io, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.environ.get("CCM_REFERENCE_DIR") or os.path.join(os.path.dirname(HERE), "reference-documents")
FORMATS = (".xlsx", ".csv", ".docx", ".md", ".txt")
# Files in the folder that describe documents rather than being one.
NOT_DOCS = ("readme.md",)
ABOUT_SUFFIX = ".about.md"

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class RefError(Exception):
    pass


# ---------- readers: each returns {table_name: (header, rows)} ----------

def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path):
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    shared = []
    if "xl/sharedStrings.xml" in names:
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_M + "si"):
            shared.append("".join(t.text or "" for t in si.iter(_M + "t")))
    rels = {r.get("Id"): r.get("Target") for r in
            ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(_PR + "Relationship")}
    tables = {}
    for sheet in ET.fromstring(z.read("xl/workbook.xml")).iter(_M + "sheet"):
        target = rels[sheet.get(_R + "id")]
        target = target.lstrip("/") if target.startswith("/") else "xl/" + target
        grid = []
        for row in ET.fromstring(z.read(target)).iter(_M + "row"):
            cells = {}
            for c in row.iter(_M + "c"):
                kind, v = c.get("t"), c.find(_M + "v")
                if kind == "s" and v is not None:
                    val = shared[int(v.text)]
                elif kind == "inlineStr":
                    val = "".join(t.text or "" for t in c.iter(_M + "t"))
                else:
                    val = v.text if v is not None else ""
                cells[_col_index(c.get("r"))] = (val or "").strip()
            if any(cells.values()):
                width = max(cells) + 1
                grid.append([cells.get(i, "") for i in range(width)])
        if grid:
            header = [h or f"col{i + 1}" for i, h in enumerate(grid[0])]
            tables[sheet.get("name")] = (header, [_pad(r, len(header)) for r in grid[1:]])
    return tables


def _pad(row, n):
    return (row + [""] * n)[:n]


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        grid = [r for r in csv.reader(fh) if any(c.strip() for c in r)]
    if not grid:
        return {}
    header = [h.strip() or f"col{i + 1}" for i, h in enumerate(grid[0])]
    return {os.path.splitext(os.path.basename(path))[0]:
            (header, [_pad([c.strip() for c in r], len(header)) for r in grid[1:]])}


def read_docx(path):
    body = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    paras = ["".join(t.text or "" for t in p.iter(_W + "t")).strip() for p in body.iter(_W + "p")]
    rows = [[str(i + 1), p] for i, p in enumerate(x for x in paras if x)]
    return {"Paragraphs": (["#", "Text"], rows)}


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    rows, title, buf = [], "(start)", []
    for line in text.splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            if "".join(buf).strip():
                rows.append([title, "\n".join(buf).strip()])
            title, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        rows.append([title, "\n".join(buf).strip()])
    return {"Sections": (["Section", "Text"], rows)}


READERS = {".xlsx": read_xlsx, ".csv": read_csv, ".docx": read_docx, ".md": read_text, ".txt": read_text}


# ---------- lookup ----------

def documents(docs_dir=None):
    d = docs_dir or DOCS_DIR
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        low = name.lower()
        if low in NOT_DOCS or low.endswith(ABOUT_SUFFIX) or name.startswith("."):
            continue
        if os.path.splitext(low)[1] in FORMATS:
            out.append(os.path.join(d, name))
    return out


def find_doc(query, docs_dir=None):
    docs = documents(docs_dir)
    q = query.lower()
    for exact in (lambda b: b == q, lambda b: os.path.splitext(b)[0] == q, lambda b: q in b):
        hits = [p for p in docs if exact(os.path.basename(p).lower())]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise RefError(f"'{query}' matches several documents: "
                           + ", ".join(os.path.basename(h) for h in hits))
    raise RefError(f"no reference document matches '{query}'. Run 'ref_docs.py list'.")


def load(path):
    return READERS[os.path.splitext(path)[1].lower()](path)


def pick(name, options, what):
    q = name.lower()
    exact = [o for o in options if o.lower() == q]
    if exact:
        return exact[0]
    hits = [o for o in options if o.lower().startswith(q)] or [o for o in options if q in o.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise RefError(f"no {what} matches '{name}'. Options: {', '.join(options)}")
    raise RefError(f"'{name}' matches several {what}s: {', '.join(hits)}")


def about(path):
    side = os.path.splitext(path)[0] + ABOUT_SUFFIX
    if not os.path.exists(side):
        return None
    with open(side, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def _clip(value, n):
    value = value.replace("\r", "")
    return value if n <= 0 or len(value) <= n else value[:n].rstrip() + " …"


def _format(table, header, row, cols, max_chars, row_no):
    idx = range(len(header)) if not cols else [header.index(c) for c in cols]
    lines = [f"--- {table} · row {row_no}"]
    for i in idx:
        if row[i]:
            val = _clip(row[i], max_chars)
            lines.append(f"{header[i]}: " + (val if "\n" not in val else "\n  " + val.replace("\n", "\n  ")))
    return "\n".join(lines)


def _resolve_cols(spec, header):
    return [pick(c.strip(), header, "column") for c in spec.split(",")] if spec else None


# ---------- commands ----------

def cmd_list(a):
    docs = documents()
    if not docs:
        print(f"No reference documents yet in {DOCS_DIR}.")
        return 0
    for p in docs:
        tables = load(p)
        print(os.path.basename(p))
        summary = about(p)
        if summary:
            print(f"  {summary}")
        for t, (h, rows) in tables.items():
            print(f"  · {t}: {len(rows)} rows, {len(h)} columns")
    return 0


def cmd_schema(a):
    path = find_doc(a.doc)
    print(os.path.basename(path))
    for t, (header, rows) in load(path).items():
        print(f"\n[{t}] {len(rows)} rows")
        for i, col in enumerate(header):
            values = {r[i] for r in rows if r[i]}
            if 0 < len(values) <= 12 and all(len(v) <= 40 for v in values):
                print(f"  {col}: one of {', '.join(sorted(values))}")
            else:
                print(f"  {col}: free text ({len(values)} distinct)")
    return 0


def _emit(results, total, limit):
    for r in results:
        print(r)
    if total == 0:
        print("No matching rows.")
    elif total > len(results):
        print(f"\n… {total - len(results)} more matching rows (raise --limit or narrow the search).")
    else:
        print(f"\n{total} matching row(s).")


def cmd_search(a):
    paths = documents() if a.doc.lower() == "all" else [find_doc(a.doc)]
    terms = [t.lower() for t in a.terms]
    results, total = [], 0
    for p in paths:
        for t, (header, rows) in load(p).items():
            if a.sheet and t != pick(a.sheet, list(load(p)), "sheet"):
                continue
            cols = _resolve_cols(a.cols, header)
            for n, row in enumerate(rows, start=2):
                hay = " ".join(row).lower()
                if all(term in hay for term in terms):
                    total += 1
                    if len(results) < a.limit:
                        label = t if len(paths) == 1 else f"{os.path.basename(p)} › {t}"
                        results.append(_format(label, header, row, cols, a.max_chars, n))
    _emit(results, total, a.limit)
    return 0


def cmd_rows(a):
    path = find_doc(a.doc)
    tables = load(path)
    table = pick(a.sheet, list(tables), "sheet")
    header, rows = tables[table]
    conds = []
    for w in a.where:
        if "=" not in w:
            raise RefError(f"--where needs Column=Value, got '{w}'")
        col, val = w.split("=", 1)
        conds.append((header.index(pick(col.strip(), header, "column")), val.strip().lower()))
    cols = _resolve_cols(a.cols, header)
    results, total = [], 0
    for n, row in enumerate(rows, start=2):
        if all(row[i].lower() == v for i, v in conds):
            total += 1
            if len(results) < a.limit:
                results.append(_format(table, header, row, cols, a.max_chars, n))
    _emit(results, total, a.limit)
    return 0


def cmd_values(a):
    tables = load(find_doc(a.doc))
    table = pick(a.sheet, list(tables), "sheet")
    header, rows = tables[table]
    i = header.index(pick(a.col, header, "column"))
    counts = {}
    for r in rows:
        if r[i]:
            counts[r[i]] = counts.get(r[i], 0) + 1
    print(f"{table} › {header[i]}: {len(counts)} distinct")
    for v, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {n:>4}  {_clip(v, a.max_chars)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("schema"); s.add_argument("doc")
    v = sub.add_parser("values"); v.add_argument("doc")
    v.add_argument("--sheet", required=True); v.add_argument("--col", required=True)
    v.add_argument("--max-chars", type=int, default=200)
    for name in ("search", "rows"):
        p = sub.add_parser(name)
        p.add_argument("doc")
        if name == "search":
            p.add_argument("terms", nargs="+")
            p.add_argument("--sheet")
        else:
            p.add_argument("--sheet", required=True)
            p.add_argument("--where", action="append", default=[])
        p.add_argument("--cols")
        p.add_argument("--limit", type=int, default=5)
        p.add_argument("--max-chars", type=int, default=600)
    a = ap.parse_args(argv)
    try:
        return {"list": cmd_list, "schema": cmd_schema, "search": cmd_search, "rows": cmd_rows,
                "values": cmd_values}[a.cmd](a)
    except RefError as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
