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

# --only: the incremental diff keeps this PR's files and drops what a merge of main brought in
printf 'diff --git a/lib/a.dart b/lib/a.dart\n--- a/lib/a.dart\n+++ b/lib/a.dart\n@@ -1 +1 @@\n-x\n+MINE\ndiff --git a/other/z.dart b/other/z.dart\n--- a/other/z.dart\n+++ b/other/z.dart\n@@ -1 +1 @@\n-x\n+FROM-MAIN\ndiff --git a/old.dart b/lib/renamed.dart\nsimilarity index 90%%\n@@ -1 +1 @@\n-x\n+RENAMED\n' > "$T/inc.raw"
printf 'lib/a.dart\nlib/renamed.dart\n' > "$T/only.txt"
python3 "$SCRIPTS/diff-fallback.py" --only "$T/only.txt" "$T/inc.raw" "$T/inc.patch" || fail "--only exit"
grep -q MINE "$T/inc.patch" && grep -q RENAMED "$T/inc.patch" || fail "--only dropped a PR file"; pass "--only keeps the PR's files (renames too)"
grep -q FROM-MAIN "$T/inc.patch" && fail "--only kept a file outside the PR"; pass "--only drops files outside the PR"
# fetch-context.sh must survive an old gh: an unknown --json field fails the whole
# `gh pr view` there, which stopped every review in production (2026-11-11).
OLDGH="$(mktemp -d)"
cat > "$OLDGH/gh" <<'SH'
#!/usr/bin/env bash
KNOWN=" number title body author labels additions deletions changedFiles headRefOid baseRefName state url "
if [ "$1 $2" = "pr view" ]; then
  while [ $# -gt 0 ]; do
    if [ "$1" = "--json" ]; then
      for f in ${2//,/ }; do
        case "$KNOWN" in *" $f "*) ;; *) echo "Unknown JSON field: \"$f\"" >&2; exit 1 ;; esac
      done
    fi
    shift
  done
  echo '{"number":7,"title":"t","body":"","author":{"login":"a"},"labels":[],"additions":0,"deletions":0,"changedFiles":0,"headRefOid":"abc","baseRefName":"main"}'
  exit 0
fi
[ "$1 $2" = "api graphql" ] && { echo "graphql down" >&2; exit 1; }
[ "$1" = "api" ] && { echo "[]"; exit 0; }
exit 0
SH
chmod +x "$OLDGH/gh"
OUT="$(PATH="$OLDGH:$PATH" PRR_DIR="$OLDGH/run" HEAD_SHA=abc bash "$SCRIPTS/fetch-context.sh" o/r 7 base123 bot 2>&1)"; RC=$?
echo "$OUT" | grep -q 'ERROR=cannot read PR' && fail "fetch-context asks gh pr view for a field old gh does not know (got: $OUT)"
[ -s "$OLDGH/run/pr.json" ] || fail "pr.json staged with an old gh (rc=$RC, got: $OUT)"
[ -e "$OLDGH/run/linked-issues.md" ] || fail "a failing linked-issue lookup must not stop staging"
pass "fetch-context works with an old gh and without linked issues"
if grep -rn -- '--json' "$SCRIPTS"/*.sh | grep -q 'closingIssuesReferences'; then fail "closingIssuesReferences must not be a gh --json field"; fi
pass "no gh --json field newer than the container's gh"
rm -rf "$OLDGH"
echo "ALL PASS"
