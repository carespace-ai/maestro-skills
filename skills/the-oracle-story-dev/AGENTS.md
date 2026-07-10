# The Oracle — Story Dev (single-story BMAD, backlog-file-driven)

> Develops ONE BMAD story at a time, parsed out of a monolithic `stories-output.md` in `carespace-ai/the-oracle-backlog`, across every repo in that story's `repos_affected`, opening one PR per repo per story. Owns the single-story workflow; deliberately not project-wide.

Prompt + shell skill: `SKILL.md`, `REFERENCE.md`, `scripts/` (`parse-stories.py`,
`sprint-status.py`, `multigitter-pr.sh`) and `templates/sprint-status.yaml`.

## Scope

**Owns**:
- Parse a single `Epic.Story` (e.g. `2.4`) from the backlog's `stories-output.md`.
- Manage a **local sprint manifest** (`sprint-status.yaml`) tracking story state.
- Implement that one story across each repo in its `repos_affected` frontmatter.
- Open one PR per repo per story via multi-gitter — branch `bmad/<feature>/story-<epic.story>`.

**Does NOT own**: project-wide implementation (hand off to `oracle-pipeline`); GitHub-issue-driven dev (`the-oracle-development`, one issue → one PR); story authoring; the backlog file itself.

## Dependencies

### This System Depends On

| System | What's Used | Contract |
|--------|-------------|----------|
| the-oracle-backlog | `stories-output.md` (source of stories) | Read directly from `carespace-ai/the-oracle-backlog` |
| `multi-gitter` | one PR per repo per story | Shell binary; `scripts/multigitter-pr.sh` |
| `gh` CLI + `git` | branch/commit/push/PR | Shell; `GITHUB_TOKEN` |
| `python3` | `parse-stories.py`, `sprint-status.py` | Shell |
| `Task` tool | parallel per-repo work | Subagent fan-out (see `SUBAGENT-PATTERNS.md`) |

### Systems That Depend On This

| System | How It's Used |
|--------|---------------|
| Chat / ClaudeHub invocation | Entry point ("develop story 2.4", "next ready story in <feature>") |
| (nothing internal) | Distinct workflow; no sibling skill imports it |

## Integration Points

### → target repos (repos_affected)
**What's passed**: branch `bmad/<feature>/story-<id>`, one PR per repo. **Who owns lifecycle**: this skill through PR open; merge is out of scope. **Contract**: one story = one branch = one PR per affected repo.

### ← the-oracle-backlog
**What's received**: story body + `repos_affected` frontmatter parsed from `stories-output.md`. **Expectations**: story ID resolvable; backlog file is authoritative and read-only here.

## Initialization & Lifecycle

**Created by**: `CLAUDEHUB_INPUT_KWARGS` JSON envelope OR direct chat. **Lifecycle**: ephemeral per story; persistent state is the local `sprint-status.yaml` manifest + the opened PRs. Boundary table in `SKILL.md` routes project-wide requests to `oracle-pipeline`.

## Ownership

| Thing | Relationship | Notes |
|-------|--------------|-------|
| `bmad/<feature>/story-<id>` branches + PRs | **Owns** | One per repo per story |
| `sprint-status.yaml` manifest | **Owns** | Local sprint state tracker |
| `stories-output.md` | **Borrows** | Read-only from backlog |

## State

**Holds**: local sprint manifest (`sprint-status.yaml`) mapping stories → state. **Mutable**: manifest as stories progress. **Immutable**: a story's `Epic.Story` ID and `repos_affected`.

## Key Invariants

- **Must**: operate on exactly ONE story per invocation — refuse project-wide requests (hand off to `oracle-pipeline`).
- **Must**: branch name is `bmad/<feature>/story-<epic.story>`; one PR per repo in `repos_affected`.
- **Assumes**: the story's `repos_affected` frontmatter is present and accurate.

## Patterns

```bash
# One story, N repos → one PR each, all sharing the story branch
bash scripts/multigitter-pr.sh "bmad/${FEATURE}/story-${STORY_ID}"
```

## Anti-patterns

```text
# ❌ Don't run this for "implement the whole project" — wrong granularity
# ✅ Do hand off to oracle-pipeline for anchor-issue project-wide work
```
