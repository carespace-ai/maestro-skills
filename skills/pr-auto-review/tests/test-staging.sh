#!/usr/bin/env bash
# Context assembly + diff fallback — nothing is silently dropped, nothing unreadable looks reviewed.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"
kv() { echo "$1" | sed -n "s/^$2=//p"; }

# ── context-assemble.py ──────────────────────────────────────────────────────
python3 - "$T" <<'PY'
import sys
t = sys.argv[1]
filler = "lorem ipsum dolor sit amet\n" * 400          # ~10.8k chars
open(f"{t}/root.md", "w").write(
    "# repo\n\n## What this repo is\nintro\n\n## Conventions\n" + filler * 3 +
    "\n## App Integration\n| mobile | backend | REST |\nROOT-INTEGRATION-RULE\n\n## Docs map\nlinks\n")
open(f"{t}/small.md", "w").write("# lib/a\n\n## Key Invariants\nSMALL-INVARIANT\n")
open(f"{t}/big.md", "w").write(
    "# lib/b\n\n## Layout\n" + filler * 2 + "\n## Integration Contracts\nBIG-CONTRACT\n### Sub\nBIG-SUB\n\n## Testing\n" + filler)
open(f"{t}/m.tsv", "w").write(f"AGENTS.md\t{t}/root.md\nlib/a/AGENTS.md\t{t}/small.md\nlib/b/AGENTS.md\t{t}/big.md\n")
PY
OUT="$(PRR_ROOT_CAP=20000 PRR_CONTEXT_BUDGET=5000 PRR_NODE_EXCERPT=2000 python3 "$SCRIPTS/context-assemble.py" "$T/m.tsv" "$T/ctx.md" abcdef1234)"
[ "$(kv "$OUT" CONTEXT_NODES)" = 1 ] || fail "one node inlined in full (got: $OUT)"; pass "small node inlined in full"
[ "$(kv "$OUT" CONTEXT_NODES_EXCERPTED)" = 2 ] || fail "two nodes excerpted (got: $OUT)"; pass "oversized nodes excerpted, not dropped"
grep -q "ROOT-INTEGRATION-RULE" "$T/ctx.md" || fail "oversized root lost its integration section"; pass "oversized root keeps its late integration section"
grep -q "SMALL-INVARIANT" "$T/ctx.md" || fail "small node body"; pass "small node body present"
grep -q "BIG-CONTRACT" "$T/ctx.md" && grep -q "BIG-SUB" "$T/ctx.md" || fail "excerpt lost the contract section"; pass "excerpt carries contract section + subsections"
grep -q "$T/big.md" "$T/ctx.md" || fail "excerpt should point at the staged file"; pass "excerpt points at the staged file"
grep -q -- "- Testing" "$T/ctx.md" || fail "excerpt outline"; pass "excerpt lists the outline"
[ "$(wc -c < "$T/ctx.md")" -lt 40000 ] || fail "assembled context is not bounded"; pass "assembled context is bounded"

OUT="$(python3 "$SCRIPTS/context-assemble.py" "$T/m.tsv" "$T/ctx2.md" abcdef1234)"
[ "$(kv "$OUT" CONTEXT_NODES)" = 3 ] || fail "defaults should inline all three (got: $OUT)"; pass "default budgets inline everything that fits"
: > "$T/empty.tsv"
OUT="$(python3 "$SCRIPTS/context-assemble.py" "$T/empty.tsv" "$T/ctx3.md" abcdef1234)"
[ "$(kv "$OUT" CONTEXT_NODES)" = 0 ] && [ ! -s "$T/ctx3.md" ] || fail "no nodes → empty context"; pass "repo without a Context Layer"

# ── diff-fallback.py ─────────────────────────────────────────────────────────
fb() { echo "$1" > "$T/files.json"; python3 "$SCRIPTS/diff-fallback.py" "$T/files.json" "$T/d.patch" "$T/unread.txt" "${2:-}"; }
OUT="$(fb '[{"filename":"a.dart","changes":2,"patch":"@@ -1 +1 @@\n-x\n+y"},{"filename":"logo.png","changes":0}]' 2)"
[ "$(kv "$OUT" DIFF_STATUS)" = ok ] || fail "all text patches present → ok (got: $OUT)"; pass "fallback ok (binary needs no patch)"
grep -q '^+++ b/a.dart$' "$T/d.patch" || fail "stitched diff header"; pass "stitched diff has file headers"
OUT="$(fb '[{"filename":"a.dart","changes":2,"patch":"@@ -1 +1 @@\n-x\n+y"},{"filename":"huge.json","changes":90000}]' 2)"
[ "$(kv "$OUT" DIFF_STATUS)" = partial ] && grep -q '^huge.json$' "$T/unread.txt" || fail "omitted patch → partial + listed (got: $OUT)"; pass "omitted patch → partial, file listed"
OUT="$(fb '[{"filename":"huge.json","changes":90000}]' 1)"
[ "$(kv "$OUT" DIFF_STATUS)" = missing ] || fail "nothing readable → missing (got: $OUT)"; pass "nothing readable → missing"
OUT="$(fb 'gh: HTTP 502' 7)"
[ "$(kv "$OUT" DIFF_STATUS)" = missing ] || fail "API error → missing (got: $OUT)"; pass "files API error → missing"
OUT="$(fb '[{"filename":"a.dart","changes":2,"patch":"@@"}][{"filename":"b.dart","changes":1,"patch":"@@"}]' 2)"
[ "$(kv "$OUT" DIFF_STATUS)" = ok ] || fail "paginated arrays (got: $OUT)"; pass "concatenated pages parsed"
OUT="$(fb '[{"filename":"a.dart","changes":2,"patch":"@@"}]' 5)"
[ "$(kv "$OUT" DIFF_STATUS)" = partial ] || fail "fewer files listed than changed → partial (got: $OUT)"; pass "short file list → partial"
[ "$(python3 "$SCRIPTS/diff-fallback.py" --names "$T/files.json")" = a.dart ] || fail "--names"; pass "--names lists changed paths"
echo "ALL PASS"
