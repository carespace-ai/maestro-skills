# CodeGraph-backed Context Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewire the `context-layer` skill so every structural fact (modules, dependencies both directions, integration map) comes from the CodeGraph CLI instead of `find`/`grep`, while prose (intent, invariants, ownership) stays LLM-authored.

**Architecture:** A per-run CodeGraph index is built on the freshly-cloned repo; a thin `cg.sh` verb wrapper exposes JSON queries; the three agent specs are rewritten to prefer CodeGraph and degrade to grep; the Maestro `SKILL.md` hard-fails only when a *supported*-language repo fails to index.

**Tech Stack:** Bash, `@sdsrs/code-graph` CLI (binary `code-graph`, already `npm i -g` in the Maestro image), `python3` for JSON parsing (present in the image; jq is NOT guaranteed), GitHub `gh`/`git`.

## Global Constraints

- CodeGraph binary name on PATH is **`code-graph`** (the `@sdsrs/code-graph` package installs bins `code-graph` and `code-graph-mcp`; both are `bin/cli.js`). Wrappers must allow override via `CG_BIN` env for testing.
- JSON parsing uses **`python3`**, never `jq` (jq may be absent in the Maestro image — same rule the existing `should-run.sh` follows).
- All `cg.sh` verbs emit **JSON on stdout** and use CodeGraph's **structural** commands only (`map`, `overview`, `deps`, `refs`, `callgraph`, `health-check`, `rebuild-index`) — never `search`/`similar`/`semantic_code_search`, which require an embedding-model download (network).
- The index directory is **`.code-graph/`** — it must be gitignored in every target repo (the docs PR must stay docs-only; the existing DIFF GUARD in `SKILL.md` rejects any non-docs path).
- Supported languages for the hard-fail policy: **TypeScript, JavaScript (+ TSX/JSX), Python, Go**. Any other language → grep fallback, never hard-fail.
- Commit subjects are lowercase (repo uses commitlint): `feat: ...`, `test: ...`, `docs: ...`.
- Portable specs (`tooling/agents/*.md`) must **prefer CodeGraph, fall back to grep** when `cg.sh`/`code-graph` is absent. The hard-fail rule lives ONLY in `SKILL.md`, never in the portable specs.

---

## Verified CodeGraph CLI reference (use these exact shapes)

Index lifecycle (run from inside the repo dir):

```
code-graph rebuild-index --confirm      # full build; prints "Full index: N files, N nodes, N edges"
code-graph health-check --json          # {"healthy":true,"files":2,"nodes":5,"edges":7,
                                         #  "resolution":{"edges_by_language":{"typescript":{...}}}, ...}
```

Query commands (all accept `--json`):

```
code-graph map --json
# {"modules":[{"path":"src/auth","files":1,"functions":2,"classes":0,
#              "key_symbols":["makeToken","verify"],"languages":["typescript"]}, ...],
#  "module_dependencies":[{"from":"src/api","to":"src/auth","imports":2}],
#  "hot_functions":[{"name":"makeToken","file":"src/auth/token.ts","caller_count":1}],
#  "entry_points":[]}

code-graph overview src/auth --json
# [{"name":"makeToken","signature":"(id: string) -> string","file":"src/auth/token.ts",
#   "type":"function","caller_count":1,"start_line":1,"end_line":1}, ...]

code-graph deps src/api/users.ts --direction both --json
# {"file":"src/api/users.ts",
#  "depends_on":[{"file":"src/auth/token.ts","depth":1,"symbols":2}],
#  "depended_by":[]}

code-graph refs makeToken --json
# {"symbol":"makeToken","total_references":3,"by_relation":{"calls":1,"imports":1,"exports":1},
#  "references":[{"file_path":"src/api/users.ts","name":"login","relation":"calls",
#                 "confidence":"inferred","type":"function","start_line":2}, ...]}

code-graph callgraph makeToken --direction both --json
# {"results":[{"direction":"callers","file_path":"src/api/users.ts","name":"login","depth":1,...}]}
```

---

## File Structure

**Create:**
- `skills/context-layer/tooling/cg.sh` — stable verb wrapper over the `code-graph` CLI (installed into target repos).
- `skills/context-layer/scripts/codegraph-bootstrap.sh` — build index + emit `CODEGRAPH=ready|fallback|failed`.
- `skills/context-layer/tests/lib.sh` — shared test helper: builds a tiny TS fixture repo.
- `skills/context-layer/tests/test-cg.sh` — asserts `cg.sh` verbs against the fixture.
- `skills/context-layer/tests/test-bootstrap.sh` — asserts the ready/fallback/failed decisions.

**Modify:**
- `skills/context-layer/tooling/install.sh` — copy `cg.sh` into `.claude/`; gitignore `.code-graph/`.
- `skills/context-layer/SKILL.md` — new STEP 1.5 (bootstrap + policy enforcement); STEP 2 points capture at CodeGraph.
- `skills/context-layer/tooling/agents/context-layer-capture.md` — deps via `cg deps`/`cg refs`, symbols via `cg overview`, grep fallback.
- `skills/context-layer/tooling/agents/context-layer-coordinator.md` — discovery via `cg map`; graph-verified completeness gate; review stale-ref via `cg refs`.
- `skills/context-layer/tooling/agents/context-layer-synthesis.md` — integration map/dep-direction from `cg map` `module_dependencies`.

---

### Task 1: `cg.sh` verb wrapper

**Files:**
- Create: `skills/context-layer/tooling/cg.sh`
- Create: `skills/context-layer/tests/lib.sh`
- Test: `skills/context-layer/tests/test-cg.sh`

**Interfaces:**
- Produces: an executable `cg.sh` invoked as `bash cg.sh <verb> [arg]`. Verbs: `ready` (→ health-check JSON), `index` (→ rebuild-index, human output), `map`, `overview <dir>`, `deps <file>`, `refs <symbol>`, `callgraph <symbol>`. Every query verb prints JSON to stdout. Exit `3` if `code-graph` is not on PATH; exit `2` on unknown verb. Honors `CG_BIN` override.

- [ ] **Step 1: Write the fixture helper**

Create `skills/context-layer/tests/lib.sh`:

```bash
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
}

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }
```

- [ ] **Step 2: Write the failing test**

Create `skills/context-layer/tests/test-cg.sh`:

```bash
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `bash skills/context-layer/tests/test-cg.sh`
Expected: FAIL (cg.sh does not exist yet) — e.g. `bash: .../cg.sh: No such file or directory`. (If `code-graph` isn't installed locally it prints `SKIP` and exits 0 — install it with `npm i -g @sdsrs/code-graph` to run the test for real.)

- [ ] **Step 4: Implement `cg.sh`**

Create `skills/context-layer/tooling/cg.sh`:

```bash
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
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `chmod +x skills/context-layer/tooling/cg.sh && bash skills/context-layer/tests/test-cg.sh`
Expected: `ALL PASS` (or `SKIP` if code-graph isn't installed locally).

- [ ] **Step 6: Commit**

```bash
git add skills/context-layer/tooling/cg.sh skills/context-layer/tests/lib.sh skills/context-layer/tests/test-cg.sh
git commit -m "feat: add cg.sh codegraph verb wrapper with tests"
```

---

### Task 2: `codegraph-bootstrap.sh` (index + policy decision)

**Files:**
- Create: `skills/context-layer/scripts/codegraph-bootstrap.sh`
- Test: `skills/context-layer/tests/test-bootstrap.sh`

**Interfaces:**
- Consumes: run from inside the cloned repo dir. Honors `CG_BIN`.
- Produces: prints `KEY=VALUE` lines — `NODES=<n>`, `REASON=<text>`, and a final `CODEGRAPH=ready|fallback|failed`. Exit code always `0`; callers act on `CODEGRAPH`. `ready` = index built with nodes>0; `failed` = supported-language source present but 0 nodes; `fallback` = no supported source OR binary absent.

- [ ] **Step 1: Write the failing test**

Create `skills/context-layer/tests/test-bootstrap.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
BOOT="$HERE/../scripts/codegraph-bootstrap.sh"

# Case A: binary absent → fallback (works even without code-graph installed)
A="$(mktemp -d)/repo"; make_fixture "$A"; cd "$A"
OUT="$(CG_BIN=definitely-not-a-real-bin bash "$BOOT")"
echo "$OUT" | grep -q '^CODEGRAPH=fallback$' || fail "absent binary should be fallback: $OUT"
pass "absent-binary-fallback"

command -v code-graph >/dev/null 2>&1 || { echo "SKIP rest: code-graph not installed"; echo "ALL PASS"; exit 0; }

# Case B: supported TS source → ready
B="$(mktemp -d)/repo"; make_fixture "$B"; cd "$B"
OUT="$(bash "$BOOT")"
echo "$OUT" | grep -q '^CODEGRAPH=ready$' || fail "TS fixture should be ready: $OUT"
pass "supported-ready"

# Case C: no supported source (only a .md) → fallback
C="$(mktemp -d)/repo"; mkdir -p "$C"; echo "# readme" > "$C/README.md"; cd "$C"
OUT="$(bash "$BOOT")"
echo "$OUT" | grep -q '^CODEGRAPH=fallback$' || fail "no-source repo should be fallback: $OUT"
pass "unsupported-fallback"
echo "ALL PASS"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash skills/context-layer/tests/test-bootstrap.sh`
Expected: FAIL — `codegraph-bootstrap.sh: No such file or directory`.

- [ ] **Step 3: Implement `codegraph-bootstrap.sh`**

Create `skills/context-layer/scripts/codegraph-bootstrap.sh`:

```bash
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
HAS_SRC=""
if find . -type f \
     \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' \
        -o -name '*.py' -o -name '*.go' \) \
     ! -path '*/node_modules/*' ! -path '*/.git/*' ! -path '*/dist/*' 2>/dev/null \
   | head -1 | grep -q . ; then HAS_SRC=1; fi

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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `chmod +x skills/context-layer/scripts/codegraph-bootstrap.sh && bash skills/context-layer/tests/test-bootstrap.sh`
Expected: `ALL PASS` (Case A always runs; B/C run when code-graph is installed).

- [ ] **Step 5: Commit**

```bash
git add skills/context-layer/scripts/codegraph-bootstrap.sh skills/context-layer/tests/test-bootstrap.sh
git commit -m "feat: add codegraph-bootstrap with ready/fallback/failed policy"
```

---

### Task 3: Install `cg.sh` into target repos + gitignore the index

**Files:**
- Modify: `skills/context-layer/tooling/install.sh`

**Interfaces:**
- Consumes: `cg.sh` from Task 1 (sibling of `install.sh` under `tooling/`).
- Produces: after `install.sh <repo>`, the repo has `.claude/cg.sh` (executable) and `.gitignore` contains `.code-graph/`.

- [ ] **Step 1: Write the failing test (inline check)**

Run this now to confirm current behavior lacks the new wiring:

```bash
T="$(mktemp -d)/repo"; mkdir -p "$T"; git -C "$T" init -q
bash skills/context-layer/tooling/install.sh "$T"
test -f "$T/.claude/cg.sh" && echo "HAS_CG" || echo "NO_CG"
grep -q '^\.code-graph' "$T/.gitignore" 2>/dev/null && echo "HAS_IGNORE" || echo "NO_IGNORE"
```

Expected: `NO_CG` and `NO_IGNORE` (before the change).

- [ ] **Step 2: Modify `install.sh`**

In `skills/context-layer/tooling/install.sh`, after the block that `cp`s the skills into `$TARGET/.claude/skills/`, add the `cg.sh` copy:

```bash
# CodeGraph verb wrapper — agents call `bash .claude/cg.sh <verb>` for structural facts.
cp "$HERE/cg.sh" "$TARGET/.claude/cg.sh"
chmod +x "$TARGET/.claude/cg.sh"
```

And extend the existing `.gitignore` block so BOTH the manifest dir and the index dir are ignored. Replace the existing gitignore stanza:

```bash
if [ -f "$TARGET/.gitignore" ]; then
  grep -q '^\.context-layer' "$TARGET/.gitignore" || echo '.context-layer/' >> "$TARGET/.gitignore"
else
  echo '.context-layer/' > "$TARGET/.gitignore"
fi
```

with:

```bash
touch "$TARGET/.gitignore"
grep -q '^\.context-layer' "$TARGET/.gitignore" || echo '.context-layer/' >> "$TARGET/.gitignore"
grep -q '^\.code-graph'    "$TARGET/.gitignore" || echo '.code-graph/'    >> "$TARGET/.gitignore"
```

Also update the final `echo` line to mention `cg.sh`:

```bash
echo "installed context-layer tooling into $TARGET/.claude/ (agents: coordinator, capture, synthesis; skills: context-layer, add-rule; cg.sh)"
```

- [ ] **Step 3: Run the check to verify it passes**

Run:

```bash
T="$(mktemp -d)/repo"; mkdir -p "$T"; git -C "$T" init -q
bash skills/context-layer/tooling/install.sh "$T"
test -x "$T/.claude/cg.sh" && echo "HAS_CG"
grep -q '^\.code-graph' "$T/.gitignore" && echo "HAS_IGNORE"
grep -q '^\.context-layer' "$T/.gitignore" && echo "HAS_CTX"
```

Expected: `HAS_CG`, `HAS_IGNORE`, `HAS_CTX` all printed.

- [ ] **Step 4: Commit**

```bash
git add skills/context-layer/tooling/install.sh
git commit -m "feat: install cg.sh into repos and gitignore .code-graph"
```

---

### Task 4: SKILL.md — bootstrap step + hard-fail policy

**Files:**
- Modify: `skills/context-layer/SKILL.md`

**Interfaces:**
- Consumes: `scripts/codegraph-bootstrap.sh` (Task 2); `tooling/install.sh` now ships `cg.sh` (Task 3).
- Produces: `SKILL.md` gains a STEP 1.5 that sets `CODEGRAPH` mode and hard-exits on `failed`, and STEP 2 tells the inline coordinator to use CodeGraph when `CODEGRAPH=ready`.

- [ ] **Step 1: Add STEP 1.5 after the STEP 1 clone block**

In `skills/context-layer/SKILL.md`, immediately before `## STEP 2 — Regenerate the Context Layer`, insert:

````markdown
## STEP 1.5 — CodeGraph bootstrap (decide graph-backed vs grep)

From **inside the cloned repo**, build the CodeGraph index and read the run mode.
The guard lives next to this SKILL.md:

```bash
BOOT="$HOME/.claude/skills/context-layer/scripts/codegraph-bootstrap.sh"
[ -f "$BOOT" ] || BOOT="$(find "$HOME/.claude/skills" /app -name codegraph-bootstrap.sh -path '*context-layer*' 2>/dev/null | head -1)"
# Capture output and parse the KEY=VALUE lines WITHOUT sourcing — REASON contains
# spaces, so `source <(...)` would try to execute words as commands.
BOOT_OUT="$(bash "$BOOT")"
CODEGRAPH="$(printf '%s\n' "$BOOT_OUT" | sed -n 's/^CODEGRAPH=//p' | tail -1)"
REASON="$(printf '%s\n'  "$BOOT_OUT" | sed -n 's/^REASON=//p'  | tail -1)"
NODES="$(printf '%s\n'   "$BOOT_OUT" | sed -n 's/^NODES=//p'   | tail -1)"
echo "CodeGraph: $CODEGRAPH ($REASON)"

case "$CODEGRAPH" in
  ready)    export CONTEXT_LAYER_CODEGRAPH=ready ;;   # agents query the graph via .claude/cg.sh
  fallback) export CONTEXT_LAYER_CODEGRAPH=fallback ;; # unsupported language → grep paths
  failed)   echo "ABORT: CodeGraph failed to index a supported-language repo ($REASON)"; exit 1 ;;
esac
```

- `ready` → the capture/synthesis steps below MUST source structural facts from
  `bash .claude/cg.sh <verb>` (installed by `tooling/install.sh`).
- `fallback` → use the grep/find paths documented in the agent specs.
- `failed` → **hard-fail the run** (a supported repo that won't index is a
  regression to fix, not a silent quality drop). This is the ONLY place the
  hard-fail policy is enforced; the portable specs always degrade gracefully.
````

- [ ] **Step 2: Point STEP 2 at CodeGraph**

In `SKILL.md` STEP 2, inside the bullet that begins **"Capture**: for each system, read its real source (+ grep who-imports-what)…"**, replace that parenthetical with:

```markdown
   - **Capture**: for each system, get its symbols/signatures from
     `bash .claude/cg.sh overview <dir>` and its dependency edges from
     `bash .claude/cg.sh deps <file>` / `bash .claude/cg.sh refs <symbol>`
     when `CONTEXT_LAYER_CODEGRAPH=ready`; otherwise fall back to reading source
     + `grep` who-imports-what. Write `<system>/AGENTS.md` in the capture.md leaf
     format (Scope, Dependencies BOTH directions, Integration Points, Lifecycle,
     Ownership, State, Key Invariants, Patterns, Anti-patterns; ≤~2000 tokens; do
     not invent).
```

And in the same STEP 2, in the **Discover** bullet, after "First list every candidate unit", add:

```markdown
     When `CONTEXT_LAYER_CODEGRAPH=ready`, seed this list from
     `bash .claude/cg.sh map` (`.modules[].path`) so the module inventory is
     graph-derived, not guessed; the completeness self-check below compares
     against that same list.
```

- [ ] **Step 3: Verify the edits landed**

Run:

```bash
grep -q 'STEP 1.5 — CodeGraph bootstrap' skills/context-layer/SKILL.md && echo OK_STEP15
grep -q 'cg.sh overview' skills/context-layer/SKILL.md && echo OK_CAPTURE
grep -q 'cg.sh map' skills/context-layer/SKILL.md && echo OK_DISCOVER
grep -q 'ABORT: CodeGraph failed' skills/context-layer/SKILL.md && echo OK_HARDFAIL
```

Expected: `OK_STEP15`, `OK_CAPTURE`, `OK_DISCOVER`, `OK_HARDFAIL`.

- [ ] **Step 4: Commit**

```bash
git add skills/context-layer/SKILL.md
git commit -m "feat: bootstrap codegraph and enforce hard-fail policy in SKILL.md"
```

---

### Task 5: Rewrite the capture spec (deps + symbols via CodeGraph)

**Files:**
- Modify: `skills/context-layer/tooling/agents/context-layer-capture.md`

**Interfaces:**
- Consumes: `bash .claude/cg.sh overview|deps|refs|callgraph`.
- Produces: capture spec whose "List Files", "Discover Dependencies", and "Verify Existing Documentation" phases prefer CodeGraph and fall back to grep. Output format (AGENTS.md sections) is unchanged.

- [ ] **Step 1: Replace Phase 1 "List Files" / "Read All Source Files"**

In `context-layer-capture.md`, replace the `### List Files` and `### Read All Source Files` blocks with:

````markdown
### List Files & Symbols

**If `.claude/cg.sh` is present (CodeGraph ready):** get the module's symbols and
signatures without reading every file:

```bash
bash .claude/cg.sh overview [target]     # [{name,signature,file,type,caller_count,...}]
```

Read the actual source only for the **semantic** facts CodeGraph can't give you
(invariants, comments, lifecycle) — prefer entry/service/repository files.

**Fallback (no cg.sh):** list and read source directly. The fallback exists FOR
languages CodeGraph doesn't index, so keep this extension set a superset of the
graph path — never drop the original languages (swift/rust/java):

```bash
find [target] -type f \( -name "*.swift" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.java" \) ! -path "*/test*"
```
````

- [ ] **Step 2: Replace Phase 2 "Discover Dependencies"**

Replace the `## Phase 2: Discover Dependencies` body (both the "DEPENDS ON" and "DEPENDS ON This System" grep blocks) with:

````markdown
## Phase 2: Discover Dependencies

**REQUIRED**: Both dependency tables MUST be populated. If truly empty, write "None identified."

**If CodeGraph is ready**, use exact AST edges instead of grep:

```bash
# What this system DEPENDS ON (outgoing) and what DEPENDS ON it (incoming),
# per representative file in the module:
bash .claude/cg.sh deps [target]/<entry-file>     # {depends_on:[{file,symbols}], depended_by:[{file,symbols}]}

# Reverse edges for a specific exported symbol (who calls / imports it):
bash .claude/cg.sh refs <ExportedSymbol>          # references[] with relation calls|imports|exports
bash .claude/cg.sh callgraph <ExportedSymbol>     # callers + callees
```

Map the JSON to the two tables: `depends_on` / `callees` → **This System Depends On**;
`depended_by` / `refs.references[relation in (calls,imports)]` → **Systems That
Depend On This**. CodeGraph catches re-exports and aliased imports that grep misses.

**Fallback (no cg.sh):** grep for imports and usages:

```bash
grep -r "^import\|^from\|^require" [target] | grep -v "node_modules\|test"   # depends on
# depended on by — keep the include set broad (fallback covers unsupported langs):
grep -r "[system_name]" [project_root] --include="*.swift" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.py" --include="*.go" --include="*.rs" --include="*.java" | grep -v "[target]"
```
````

- [ ] **Step 3: Update Phase 2.5 stale-consumer verification**

In `## Phase 2.5: Verify Existing Documentation (Updates Only)`, replace the grep verification with a CodeGraph-first version:

````markdown
2. For each claimed consumer, verify the edge still exists:
   ```bash
   # CodeGraph ready: the consumer is stale iff no reference remains
   bash .claude/cg.sh refs [this_system_symbol] | \
     python3 -c 'import sys,json; d=json.load(sys.stdin); print("\n".join(r["file_path"] for r in d["references"]))'
   # Fallback (broad include set — covers languages CodeGraph does not index):
   grep -r "[this_system]" [claimed_consumer_path] --include="*.swift" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.py" --include="*.go" --include="*.rs" --include="*.java"
   ```
````

- [ ] **Step 4: Verify the edits landed**

Run:

```bash
f=skills/context-layer/tooling/agents/context-layer-capture.md
grep -q 'cg.sh overview' "$f" && echo OK_OVERVIEW
grep -q 'cg.sh deps' "$f" && echo OK_DEPS
grep -q 'cg.sh refs' "$f" && echo OK_REFS
grep -q 'Fallback (no cg.sh)' "$f" && echo OK_FALLBACK
```

Expected: `OK_OVERVIEW`, `OK_DEPS`, `OK_REFS`, `OK_FALLBACK`.

- [ ] **Step 5: Commit**

```bash
git add skills/context-layer/tooling/agents/context-layer-capture.md
git commit -m "feat: capture dependencies via codegraph with grep fallback"
```

---

### Task 6: Rewrite coordinator discovery + review (map + refs)

**Files:**
- Modify: `skills/context-layer/tooling/agents/context-layer-coordinator.md`

**Interfaces:**
- Consumes: `bash .claude/cg.sh map` (discovery), `bash .claude/cg.sh refs` (review stale check).
- Produces: coordinator whose Phase 1A discovery seeds the module list from `cg map` and whose Review-mode stale check uses `cg refs`, both with grep fallback.

- [ ] **Step 1: Add a CodeGraph-first discovery block**

In `context-layer-coordinator.md`, in `## Phase 1A`, immediately under `### Discover Systems (SPEND TOKENS HERE)`, insert:

````markdown
**Seed the candidate list from CodeGraph first (if `.claude/cg.sh` is present):**

```bash
bash .claude/cg.sh map | python3 -c 'import sys,json; d=json.load(sys.stdin);
[print(m["path"], m.get("functions",0), "fns", m.get("classes",0), "cls") for m in d["modules"]]'
```

`map.modules[]` is the AST-derived module inventory — use it as the ground-truth
denominator for the completeness gate (below). `map.module_dependencies[]` already
gives the cross-module import edges you would otherwise grep for. Only fall back to
`find`/file-sampling when `cg.sh` is absent (unsupported language).
````

- [ ] **Step 2: Make the completeness gate graph-verified**

In the same file, find the discovery output section (the `📊 System Discovery` block near `### Output Discovery`) and append this line to it:

````markdown
When CodeGraph is ready, print `covered=<n>/<total>` where `<total>` is
`len(map.modules)` — every module in `cg map` must be either captured or explicitly
excluded (pure UI/asset/type/generated/test/config). A graph module with real logic
and no node is a bug.
````

- [ ] **Step 3: Update Review-mode stale check**

In `## Mode: Review Context Layer`, `### Step 3: Check for Stale References`, replace the grep with a CodeGraph-first version:

````markdown
For each "Systems That Depend On This" / "Consumed By" entry, verify the edge:

```bash
# CodeGraph ready: stale iff the symbol has no remaining references
bash .claude/cg.sh refs [claimed_symbol] | \
  python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["total_references"])'
# Fallback (broad include set — covers languages CodeGraph does not index):
grep -r "[claimed_consumer]" [project_root] --include="*.swift" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.py" --include="*.go" --include="*.rs" --include="*.java" | head -1
```

If CodeGraph reports `0` references (or grep finds no matches) → mark as stale.
````

- [ ] **Step 4: Verify the edits landed**

Run:

```bash
f=skills/context-layer/tooling/agents/context-layer-coordinator.md
grep -q 'cg.sh map' "$f" && echo OK_MAP
grep -q 'covered=<n>/<total>' "$f" && echo OK_GATE
grep -q 'cg.sh refs' "$f" && echo OK_REFS
```

Expected: `OK_MAP`, `OK_GATE`, `OK_REFS`.

- [ ] **Step 5: Commit**

```bash
git add skills/context-layer/tooling/agents/context-layer-coordinator.md
git commit -m "feat: coordinator discovery and review use codegraph map/refs"
```

---

### Task 7: Rewrite synthesis integration map (from `cg map`)

**Files:**
- Modify: `skills/context-layer/tooling/agents/context-layer-synthesis.md`

**Interfaces:**
- Consumes: `bash .claude/cg.sh map` (`module_dependencies`, `modules`).
- Produces: synthesis whose Phase 2 integration map / dependency direction is built from CodeGraph edges (with the existing prose-aggregation kept as fallback).

- [ ] **Step 1: Replace Phase 2 "Aggregate Dependencies"**

In `context-layer-synthesis.md`, under `## Phase 2: Build System Integration Map` → `### Aggregate Dependencies`, insert this before the existing prose example:

````markdown
**Build the map from CodeGraph edges when `.claude/cg.sh` is present** — this is
exact and avoids re-deriving structure from captured prose:

```bash
bash .claude/cg.sh map | python3 -c 'import sys,json; d=json.load(sys.stdin);
edges=d["module_dependencies"];
[print(f"{e[\"from\"]} -> {e[\"to\"]} ({e[\"imports\"]} imports)") for e in edges]'
```

`module_dependencies[]` gives the directed edges between modules; use them for the
System Map, **Dependency Direction**, and layer grouping (top = nothing depends on
it; bottom = many depend on it). `modules[].key_symbols` names each module's public
surface. Only aggregate from captured AGENTS.md prose when CodeGraph is unavailable.
````

- [ ] **Step 2: Note graph-sourced dependency direction**

In `## Phase 4: Document Architecture`, under the `## Dependency Direction` guidance, add:

````markdown
> When CodeGraph is ready, derive the arrows directly from `cg map`
> `module_dependencies[]` (from → to). Do not hand-infer directions that
> contradict the graph; the graph is ground truth for structure.
````

- [ ] **Step 3: Verify the edits landed**

Run:

```bash
f=skills/context-layer/tooling/agents/context-layer-synthesis.md
grep -q 'cg.sh map' "$f" && echo OK_MAP
grep -q 'module_dependencies' "$f" && echo OK_EDGES
grep -q 'graph is ground truth' "$f" && echo OK_TRUTH
```

Expected: `OK_MAP`, `OK_EDGES`, `OK_TRUTH`.

- [ ] **Step 4: Run the full test suite once more**

Run:

```bash
bash skills/context-layer/tests/test-cg.sh && bash skills/context-layer/tests/test-bootstrap.sh
```

Expected: both print `ALL PASS` (or `SKIP` lines if `code-graph` is not installed locally).

- [ ] **Step 5: Commit**

```bash
git add skills/context-layer/tooling/agents/context-layer-synthesis.md
git commit -m "feat: synthesis builds integration map from codegraph edges"
```

---

## Final verification (after all tasks)

- [ ] **Optional end-to-end smoke against a real repo** (needs `code-graph` + network to clone):

```bash
D="$(mktemp -d)"; git clone --depth 1 https://github.com/carespace-ai/maestro-skills "$D/repo"
BOOT="$PWD/skills/context-layer/scripts/codegraph-bootstrap.sh"
bash skills/context-layer/tooling/install.sh "$D/repo"
cd "$D/repo"; OUT="$(bash "$BOOT")"
CODEGRAPH="$(printf '%s\n' "$OUT" | sed -n 's/^CODEGRAPH=//p' | tail -1)"
NODES="$(printf '%s\n' "$OUT" | sed -n 's/^NODES=//p' | tail -1)"
echo "mode=$CODEGRAPH nodes=$NODES"
bash .claude/cg.sh map | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["modules"]),"modules")'
```

Expected: `mode=ready`, a positive node count, and a module count > 0.

- [ ] **shellcheck the new scripts:**

```bash
shellcheck skills/context-layer/tooling/cg.sh skills/context-layer/scripts/codegraph-bootstrap.sh skills/context-layer/tests/*.sh
```

Expected: no errors (warnings acceptable; `source <(...)` SC1090 is disabled inline in SKILL.md docs, not in these scripts).
