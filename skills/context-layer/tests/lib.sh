#!/usr/bin/env bash
# Shared test helper: create a tiny indexed TS repo and locate the code-graph binary.
set -uo pipefail

make_fixture() {
  # $1 = target dir (created fresh). Two modules with one import edge api -> auth.
  local d="$1"; rm -rf "$d"; mkdir -p "$d/src/auth" "$d/src/api"
  cat > "$d/src/auth/token.ts" <<'EOF'
export function makeToken(id: string): string { return "t-" + id; }
export function verify(t: string): boolean { return t.startsWith("t-"); }
EOF
  cat > "$d/src/api/users.ts" <<'EOF'
import { makeToken, verify } from "../auth/token";
export function login(id: string) { const t = makeToken(id); return verify(t); }
EOF
  git -C "$d" init -q
}

make_big_fixture() {
  # $1 = target dir. Many JS files under a deep path so `find`'s output exceeds the
  # ~64KB pipe buffer — this is what triggers the SIGPIPE/pipefail HAS_SRC bug that a
  # small fixture cannot. Used to regression-test codegraph-bootstrap.sh.
  local d="$1"; rm -rf "$d"
  local deep="$d/backend/services/orchestration/runners/very/deeply/nested/module/tree"
  mkdir -p "$deep"
  local i
  for i in $(seq 1 600); do
    printf 'export const a%s = %s;\n' "$i" "$i" > "$deep/some_reasonably_long_source_filename_$i.js"
  done
  git -C "$d" init -q
}

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }
