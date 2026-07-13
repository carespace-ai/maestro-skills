#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
CG="$HERE/../tooling/cg.sh"
command -v code-graph >/dev/null 2>&1 || { echo "SKIP: code-graph not installed"; exit 0; }

FIX="$(mktemp -d)/repo"; make_fixture "$FIX"; cd "$FIX"
bash "$CG" index >/dev/null 2>&1 || fail "index verb errored"

# ready → healthy JSON with nodes > 0
READY="$(bash "$CG" ready)"
echo "$READY" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d["healthy"] and d["nodes"]>0' \
  || fail "ready did not report a healthy index with nodes"
pass "ready"

# map → module list contains src/auth and a src/api->src/auth dependency
MAP="$(bash "$CG" map)"
echo "$MAP" | python3 -c 'import sys,json; d=json.load(sys.stdin);
paths={m["path"] for m in d["modules"]}; assert {"src/auth","src/api"}<=paths;
deps=[(e["from"],e["to"]) for e in d["module_dependencies"]]; assert ("src/api","src/auth") in deps' \
  || fail "map missing modules or dependency edge"
pass "map"

# deps of users.ts depends_on auth/token.ts
DEPS="$(bash "$CG" deps src/api/users.ts)"
echo "$DEPS" | python3 -c 'import sys,json; d=json.load(sys.stdin);
assert any("auth/token.ts" in x["file"] for x in d["depends_on"])' \
  || fail "deps missing depends_on edge"
pass "deps"

# refs of makeToken include a call from users.ts
REFS="$(bash "$CG" refs makeToken)"
echo "$REFS" | python3 -c 'import sys,json; d=json.load(sys.stdin);
assert any(r["relation"]=="calls" and "users.ts" in r["file_path"] for r in d["references"])' \
  || fail "refs missing caller"
pass "refs"

# unknown verb → exit 2
bash "$CG" bogus >/dev/null 2>&1; [ $? -eq 2 ] || fail "unknown verb should exit 2"
pass "unknown-verb"

# CG_BIN=missing → exit 3
CG_BIN=definitely-not-a-real-bin bash "$CG" map >/dev/null 2>&1; [ $? -eq 3 ] || fail "missing bin should exit 3"
pass "missing-bin"
echo "ALL PASS"
