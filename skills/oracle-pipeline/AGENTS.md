# Oracle Pipeline (project-wide autonomous BMAD developer + lifecycle)

> The flagship: takes a *whole* planned BMAD project (epics + stories already authored) and drives every story across every affected repo to merge-ready, then manages the resulting PR group's lifecycle. Owns the multi-repo delivery *process*; owns no product code.

This node covers two sibling skill directories that form one delivery system:
`oracle-pipeline/` (opens the PR group) and `oracle-pipeline-lifecycle/` (closes the loop:
status / merge / close / prune). Both are prompt + shell skills — a `SKILL.md` (and
`REFERENCE.md`) plus `scripts/*.sh`; bash never lives inline in the markdown.

## Scope

**Owns**:
- `oracle-pipeline` — the BMAD *developer* role: discover anchor issue → parse stories → clone target repos → per-story loop (create → dev → gates → review → commit) → open a cumulative PR group (one branch `feat/oracle-project-<slug>` per repo, dual PRs to `develop` + `master`/`main`). Phases 00–05 are `scripts/0N-*.sh`.
- `oracle-pipeline-lifecycle` — the post-open handler: group **status** (FR15 readiness), **merge** (FR17), **close** (FR18), **prune** (branch deletion after 30-day grace). Wraps multi-gitter by the shared branch name.
- Quality gates: `lint-check.sh`, `check-coverage.sh` (threshold `COVERAGE_THRESHOLD`, default 80), `pre-commit-check.sh`; spec gate `validate-issue-spec.sh`.

**Does NOT own**: story *authoring* (that is the BMAD planner / `bmad_oracle`); single-story dev (`the-oracle-story-dev`); single-issue gstack dev (`pipeline`); the product code in target repos; the GitHub Actions that invoke this skill on webhooks (live in `carespace-ai/infra`).

## Dependencies

### This System Depends On

| System | What's Used | Contract |
|--------|-------------|----------|
| `gh` CLI + `git` | clone, branch, push, PR create/merge/close, `gh api` branch probing | Shell; `GITHUB_TOKEN` auth; errors surfaced, anchor relabeled on failure |
| `multi-gitter` (lindell) | group status/merge/close/prune by `--branch <ref>` | Shell binary on PATH; selection by canonical branch name only |
| `serena` + `code-graph-mcp` | large-codebase navigation / indexing in phase 02 | MCP; opt-in per repo |
| `claude`, `jq`, `python3`, `npx` | story loop, JSON parsing, `plan-waves.py` / `extract-stories.py` | Shell; required on PATH |
| the-oracle-backlog (BMAD context) | stories + epics fetched in phase 01 | Cloned from `carespace-ai`; read-only |
| `shared/helpers.md`, `docs/multi-repo-tools.md` | named recipes; tool-choice rationale | Repo-local docs |

### Systems That Depend On This

| System | How It's Used |
|--------|---------------|
| `bmad` + `maestro-ready` anchor issues | Entry trigger — pipeline discovers and drives them |
| `carespace-ai/infra` GH Actions (when present) | Invoke lifecycle skill on meta-issue close webhook |
| (nothing internal) | Entry-point skill; no sibling skill imports it |

## Integration Points

### → target repos (carespace-ai/*)
**What's passed**: per-repo branch `feat/oracle-project-<slug>`, cumulative story diffs, dual PRs (`develop` + `master`/`main`), each `Closes #<ANCHOR>`. **Who owns lifecycle**: this system, from branch through merge/close. **Contract**: PR bodies kept in sync on re-run; test-plan checkboxes marked `[x]` only if every committed story passed that gate.

### ↔ oracle-pipeline-lifecycle (multi-gitter)
**What's passed**: `BRANCH` + `INVOLVED_REPOS` + `TARGET_ORG` via phase env files. **Contract**: one branch per project per repo (Rule 1) guarantees branch-name selection is unambiguous; status is read-only, merge/close transition the anchor label.

## Initialization & Lifecycle

**Created by**: ClaudeHub skill invocation (anchor issue with `bmad`+`maestro-ready`, or `CLAUDEHUB_INPUT_KWARGS.project_slug`). **Lifecycle**: ephemeral per run; durable state is the GitHub PR group + anchor `maestro:*` labels + `/tmp/oracle-work/` scratch (`test-plan/stories.jsonl`). **Env**: `GITHUB_TOKEN`, `TARGET_ORG` (default `carespace-ai`), optional `CLAUDEHUB_INPUT_KWARGS`, `NOTIFICATION_WEBHOOK_URL`, `COVERAGE_THRESHOLD`.

## Ownership

| Thing | Relationship | Notes |
|-------|--------------|-------|
| `feat/oracle-project-<slug>` branches + PR group | **Owns** | Creates, drives, merges/closes/prunes |
| Anchor `maestro:*` labels | **Owns** | State machine: implementing → deploying → merged |
| Target repo `develop`/`master` | **Shares** | Never pushes directly — always via PR |
| BMAD stories | **Borrows** | Read from the-oracle-backlog; does not author |

## State

**Holds**: per-run workspace under `/tmp/oracle-work/` (phase env files, `test-plan/stories.jsonl`). **Mutable**: PR bodies + labels across re-runs (idempotent). **Immutable**: the anchor issue's derived project slug.

## Key Invariants

- **Must**: exactly one branch per project per repo (`feat/oracle-project-<slug>`) — Rule 1; all multi-gitter selection depends on it.
- **Must**: a test-plan item is checked `[x]` only if it passed for **every** committed story (Rule 4); manual items stay `[ ]` with a note.
- **Never**: proceed past phase 00 if `validate-issue-spec.sh` fails — comment failures, apply `maestro:blocked-spec-incomplete`, exit 1; a human must re-apply `maestro-ready`.
- **Assumes**: `develop` exists; `master` falls back to `main` when absent (Rule 3 — dual PRs per repo).

## Patterns

```bash
# Lifecycle op = one multi-gitter call across the whole group, by branch name
multi-gitter status --branch "feat/oracle-project-${SLUG}" --repo "$INVOLVED_REPOS"
```

## Anti-patterns

```bash
# ❌ Don't wrap phase 04 (PR open) in multi-gitter — it needs per-repo bodies + dual targets
multi-gitter run --script open-prs.sh ...

# ✅ Do use the hand-rolled gh loop for open (04-open-prs.sh); multi-gitter only AFTER PRs exist
```
