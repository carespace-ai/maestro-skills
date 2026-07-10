# BMAD Oracle (product discovery & planning front-end)

> A self-contained BMAD agent bundle that guides a non-technical CEO through product discovery — Business Analyst (Mary) → Product Manager (John) → PRD/epics — producing the planning artifacts (`docs/brief.md`, `docs/prd.md`, epics) that the autonomous delivery pipelines later implement. Owns *planning*, not code.

Single-file skill: `SKILL.md` (~3.5k lines) embedding a master orchestrator persona,
role personas, and BMAD document templates as inline YAML.

## Scope

**Owns**:
- The `brief-and-prd` conversational flow: discovery session → Project Brief → PRD → epic breakdown.
- Embedded BMAD personas: `carespace-oracle-orchestrator` (router), `analyst` (Mary — research, brainstorming, brief), `pm` (John — PRD, prioritization, roadmap).
- Output templates → `docs/brief.md`, `docs/prd.md`, `docs/architecture.md`, `docs/market-research.md`, `docs/competitor-analysis.md`, `docs/brainstorming-session-results.md`.
- The epic-sequencing rules (logically sequential, each delivers deployable value) that downstream story authoring consumes.

**Does NOT own**: story implementation (that is `oracle-pipeline` / `the-oracle-story-dev`); the `stories-output.md` backlog file; any GitHub / repo mutation — this skill only writes local `docs/*.md`.

## Dependencies

### This System Depends On

| System | What's Used | Contract |
|--------|-------------|----------|
| `Read`/`Write`/`Edit`/`Bash`/`Glob`/`Grep`/`WebFetch` | doc authoring + optional web research | Local FS + web; no external service auth |
| BMAD method (embedded) | personas, templates, elicitation flow | Self-contained in `SKILL.md`; no external BMAD install |

### Systems That Depend On This

| System | How It's Used |
|--------|---------------|
| `oracle-pipeline` / `the-oracle-story-dev` | Consume the epics/PRD this produces (via the backlog once stories are authored) |
| The Oracle planning stack | Upstream artifact source (brief → PRD → epics) |
| (user / CEO) | Direct entry point — "brief", "PRD", "carespace oracle" |

## Integration Points

### → planning docs (`docs/*.md`)
**What's passed**: brief, PRD, epics as markdown files in the working repo. **Who owns lifecycle**: this skill authors them; downstream story authoring + pipelines read them. **Contract**: PRD sharding flag (`prdSharded`) decides whether epics are embedded or separate files.

### → downstream pipelines
**What's passed**: epic list + PRD that (after story authoring) become `stories-output.md` for `oracle-pipeline` / `the-oracle-story-dev`. **Contract**: handoff is via authored documents, not a live call.

## Initialization & Lifecycle

**Created by**: user trigger ("brief", "PRD", "carespace oracle", …). **Lifecycle**: interactive, multi-turn conversation; agents use "clean handoffs" (fresh context per role switch). Persistent output is the `docs/*.md` set.

## Ownership

| Thing | Relationship | Notes |
|-------|--------------|-------|
| `docs/brief.md`, `docs/prd.md`, epics | **Owns** | Authors via structured elicitation |
| Persona/template definitions | **Owns** | Embedded in `SKILL.md` |
| Downstream backlog/stories | **Shares** | Produces inputs; does not manage them |

## State

**Holds**: none persistent beyond the authored `docs/*.md`. **Mutable**: the docs across the session. **Immutable**: the BMAD templates/personas embedded in `SKILL.md`.

## Key Invariants

- **Must**: epics are logically sequential — each builds on prior ones and delivers deployable, tangible value; err toward fewer epics.
- **Must**: stay in-character per persona and use clean (fresh-context) handoffs when switching roles.
- **Assumes**: the operator is non-technical — elicitation is conversational and approval-gated (epic list approved before detail).

## Patterns

```text
User: "I have a product idea" → orchestrator routes to analyst (Mary)
  → brief.md → transform to pm (John) → prd.md + epics (approved list first)
```

## Anti-patterns

```text
# ❌ Don't implement code or touch GitHub — this skill only produces planning docs
# ✅ Do hand the approved epics/PRD to oracle-pipeline / the-oracle-story-dev
```
