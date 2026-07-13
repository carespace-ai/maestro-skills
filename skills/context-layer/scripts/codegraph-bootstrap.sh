#!/usr/bin/env bash
# codegraph-bootstrap.sh — build a CodeGraph index for the current (cloned) repo and
# decide the run mode. Run from inside the repo dir. Emits KEY=VALUE lines ending with
# CODEGRAPH=ready|fallback|failed. Exit code is always 0; the caller acts on CODEGRAPH.
#   ready    = index built, nodes > 0            → agents query the graph
#   failed   = supported-language source present but index produced 0 nodes (hard-fail upstream)
#   fallback = no supported source, or code-graph binary absent → agents use grep
set -uo pipefail
CG_BIN="${CG_BIN:-code-graph}"

emit() { printf '%s\n' "$@"; }

if ! command -v "$CG_BIN" >/dev/null 2>&1; then
  emit "REASON=code-graph binary not on PATH" "CODEGRAPH=fallback"; exit 0
fi

# Is there any source in a CodeGraph-supported language? (policy: TS/JS/Python/Go)
# Use `-print -quit` (find stops at the first match) rather than `| head -1`.
# Under `set -o pipefail`, `find ... | head -1` mislabels large repos: head closes
# the pipe after one line, find dies with SIGPIPE (exit 141), pipefail propagates
# that non-zero status, and HAS_SRC stays empty — so a big JS/TS/Python/Go repo is
# wrongly seen as "no supported source" and falls back to grep. `-print -quit` has
# no pipe, so it exits 0 cleanly regardless of repo size.
HAS_SRC=""
if [ -n "$(find . -type f \
     \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' \
        -o -name '*.py' -o -name '*.go' \) \
     ! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/dist/*' \
     -print -quit 2>/dev/null)" ]; then HAS_SRC=1; fi

# Fresh clone → full build. Never fatal here; we judge success by node count.
"$CG_BIN" rebuild-index --confirm >/dev/null 2>&1 || true

NODES="$("$CG_BIN" health-check --json 2>/dev/null \
  | python3 -c 'import sys,json;
try:
    print(int(json.load(sys.stdin).get("nodes",0)))
except Exception:
    print(0)' 2>/dev/null || echo 0)"
emit "NODES=${NODES:-0}"

# Decide by SUPPORTED-SOURCE presence FIRST, then the index result. CodeGraph
# indexes markdown/docs too (a lone README yields nodes>0), so a raw nodes>0
# check would mislabel a docs-only / unsupported-language repo as `ready`.
# Gating on HAS_SRC avoids that: no supported source → always fallback.
if [ -z "$HAS_SRC" ]; then
  emit "REASON=no CodeGraph-supported (ts/js/py/go) source detected" "CODEGRAPH=fallback"; exit 0
fi
if [ "${NODES:-0}" -gt 0 ]; then
  emit "REASON=indexed ${NODES} nodes" "CODEGRAPH=ready"; exit 0
fi
emit "REASON=supported-language source present but index produced 0 nodes" "CODEGRAPH=failed"; exit 0
