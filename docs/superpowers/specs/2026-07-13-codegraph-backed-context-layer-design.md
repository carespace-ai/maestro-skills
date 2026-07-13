# CodeGraph-backed Context Layer — Design

**Date:** 2026-07-13
**Status:** Approved (design phase)
**Skill:** `skills/context-layer` (in `carespace-ai/maestro-skills`)

## Summary

Rewire the `context-layer` skill so that **all structural facts come from
CodeGraph** (an AST-derived symbol/edge index) instead of hand-rolled
`find`/`grep`, while **prose stays LLM-authored** (intent, invariants,
ownership rationale, data-flow narration).

This solves the redundancy/ambiguity problem between the Context Layer and
CodeGraph: today both derive structure from the same source (the code), so an
auto-generated layer duplicates — and can drift from — what the graph already
knows exactly. After this change, structure is owned by CodeGraph and the layer
*extends* it with the "why" the graph cannot infer.

## Motivation & correctness win

The skill's highest-stakes output is the **bidirectional dependency tables**
in each leaf node, and today they are the least reliable:

- *depends-on* is `grep -r "^import\|^from\|^require"` — misses re-exports and
  aliased/dynamic imports.
- *depended-on-by* is `grep -r "[system_name]"` across the whole repo — noisy
  substring matches, false positives on names.

CodeGraph's `callers` / `callees` / `impact` return those edges **exactly from
the AST**. So this is a correctness upgrade, not just a token saving.

## Existing infrastructure (verified against `carespace-ai/maestro`)

- The Maestro image already installs CodeGraph: `npm install -g @sdsrs/code-graph`
  (`Dockerfile:79`). The binary is present on every run.
- Migration `0026_seed_serena_codegraph_mcp.py` seeds a `code-graph` MCP server
  (`command: code-graph-mcp`, `args: []`).
- **The seeded MCP does not help this skill.** `executor.py._write_mcp_config`
  spawns the MCP with `cwd = repo_path` (the run's workspace) and no args, so it
  indexes that cwd. The `context-layer` skill clones the *target* repo into
  `/tmp/ctx-$RANDOM/repo`, which is not that cwd — the running MCP is aimed at
  the wrong directory and cannot be re-aimed after launch.

**Conclusion:** drive CodeGraph as a **CLI against the cloned repo**, indexed
once per run, inside the skill's existing Bash flow. Deterministic; no
dependency on MCP-tool exposure inside the headless `claude -p`.

## Where CodeGraph plugs in (full pipeline)

| Stage | Today (grep/find) | New (CodeGraph) |
|---|---|---|
| coordinator — discovery | `find -type d` + sample files | file/symbol inventory grounds the module list; the `covered=n/total` completeness gate becomes graph-verified (total = real source modules from the graph) |
| capture — file/signature read | `find` + read every file | `cg files`/`node`/`explore` for symbols + signatures; read source only for semantic bits (invariants, comments) |
| capture — depends-on | `grep -r "^import"` | `cg callees` / import edges (exact) |
| capture — depended-on-by | `grep -r "[system_name]"` whole repo | `cg callers` / `cg impact` (exact reverse edges) |
| synthesis — integration map / layering / dep-direction | re-aggregate from captured prose | built directly from the repo-wide CodeGraph edge set |
| review — stale-reference check | `grep -r "[claimed_consumer]"` | `cg callers`: stale iff no edge exists |

Prose sections stay LLM-authored: Scope, Key Invariants, Integration
*contracts*, Data Flow narration, Patterns/Anti-patterns. CodeGraph cannot
infer *why*.

## New components

### `scripts/codegraph-bootstrap.sh`
Mirrors `should-run.sh`. After clone:
1. Detect the repo's primary language.
2. Classify `SUPPORTED` (TS/JS/Python/Go) vs `UNSUPPORTED`.
3. Run `codegraph index` on `/tmp/ctx.../repo` **once per run**.
4. Emit `CODEGRAPH=ready | fallback | failed` (+ `LANG`, `REASON`).

### `tooling/cg.sh`
Thin wrapper over the `@sdsrs/code-graph` CLI exposing a stable verb surface —
`cg search|files|callers|callees|impact|node` — emitting JSON. Installed into
the target repo's `.claude/` with the rest of the tooling. Isolates the exact
CLI surface so the three agent specs call `cg <verb>` in one place (and so a
future CLI change is a one-file edit).

## Policy enforcement (SKILL.md, after STEP 1 clone)

Driven by `codegraph-bootstrap.sh` output:

- `CODEGRAPH=ready` → all agents query the graph.
- `CODEGRAPH=failed` AND language is supported → **hard-fail the run** with a
  clear error (no silent quality drop on the carespace stack).
- `CODEGRAPH=fallback` (unsupported language) → agents use the existing
  grep/find paths; the docs PR still opens; the report notes fallback mode.

## Portability of the installed tooling

The coordinator/capture/synthesis specs are rewritten to **prefer CodeGraph,
degrade to grep when `cg` is unavailable**. This keeps them portable across the
contexts they run in:

- Maestro headless run — `cg` present in the image.
- A human running "Build context layer" in-repo later — CodeGraph MCP present.
- A bare checkout with neither — grep fallback.

The hard-fail-for-supported-languages rule lives **only** in the Maestro
`SKILL.md` orchestration, not in the portable specs.

## Cost & freshness

One `codegraph index` per push, reused across every module capture (not
per-module). Large repos (e.g. carespace-ui) trade per-node depth as they
already do; indexing is a fixed one-time cost per run. Incremental/partial
re-index on update pushes is deferred — full index each run for now.

## Testing

- **Smoke test:** run `codegraph-bootstrap.sh` + `cg.sh` against a small real
  repo (e.g. `maestro-skills` itself) and assert the dependency tables match
  known edges.
- **Policy tests:** unsupported-language repo → `CODEGRAPH=fallback` and grep
  path taken; supported repo with a forced index failure → hard-fail.
- `shellcheck` on both new scripts.

## To verify during implementation (not blocking design)

1. Exact `@sdsrs/code-graph` **CLI** subcommand names + JSON flags. CLAUDE.md
   documents the *MCP tool* names (`codegraph_callers`, …); the CLI binary
   surface is confirmed against the installed package. `cg.sh` isolates this —
   if the CLI is thinner than the MCP tools, only `cg.sh` changes; the fallback
   design still holds.
2. Whether `codegraph index` is a separate step or implicit on first query.

## Out of scope (deferred)

- Re-aiming the seeded MCP at the clone.
- Incremental/partial re-index on update pushes.
- Languages beyond the fallback path.
