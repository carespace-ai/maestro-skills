#!/usr/bin/env bash
# cg.sh — stable verb wrapper over the @sdsrs/code-graph CLI (binary: code-graph).
# Structural queries only; every query verb prints JSON on stdout.
# Exit codes: 0 ok, 2 unknown verb, 3 code-graph binary not on PATH.
# Override the binary with CG_BIN (used by tests).
set -uo pipefail

CG_BIN="${CG_BIN:-code-graph}"
verb="${1:-}"; shift || true

command -v "$CG_BIN" >/dev/null 2>&1 || { echo '{"error":"code-graph not installed"}'; exit 3; }

case "$verb" in
  ready)     exec "$CG_BIN" health-check --json ;;
  index)     exec "$CG_BIN" rebuild-index --confirm ;;
  map)       exec "$CG_BIN" map --json ;;
  overview)  exec "$CG_BIN" overview "${1:?overview needs a dir}" --json ;;
  deps)      exec "$CG_BIN" deps "${1:?deps needs a file}" --direction both --json ;;
  refs)      exec "$CG_BIN" refs "${1:?refs needs a symbol}" --json ;;
  callgraph) exec "$CG_BIN" callgraph "${1:?callgraph needs a symbol}" --direction both --json ;;
  *)         echo "{\"error\":\"unknown verb: ${verb}\"}"; exit 2 ;;
esac
