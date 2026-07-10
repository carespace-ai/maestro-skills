# maestro-skills — Oracle / Maestro Claude Skills

> Claude skills for the Oracle / Maestro autonomous development pipeline, plus CareSpace SecDevOps and PM automation. ClaudeHub loads skills from `skills/` and invokes them by trigger (`.claudehub.yml`). This repo is developer/automation tooling — it ships no product runtime and (per the code) handles no patient PHI directly; its skills operate *on* the CareSpace platform via `gh`, `git`, `multi-gitter`, and external APIs.

> Note: a hand-authored [`CLAUDE.md`](./CLAUDE.md) at this root is the human-facing skill index + conventions; this `AGENTS.md` is the generated Context Layer root. Both are kept.

## System Architecture

```
┌──────────────────────────────── maestro-skills (repo root) ────────────────────────────────┐
│                                                                                             │
│  CLAUDE.md · SUBAGENT-PATTERNS.md      ← human skill index + parallelization patterns        │
│  .claudehub.yml                        ← ClaudeHub job registry (which skills run, max_turns) │
│  shared/helpers.md · docs/multi-repo-tools.md  ← named recipes + tool-choice rationale        │
│                                                                                             │
│  skills/  ── six functional systems (see skills/AGENTS.md) ──                                 │
│    Planning (bmad_oracle) · Autonomous Delivery (oracle-pipeline+lifecycle,                   │
│    the-oracle-story-dev, pipeline) · SecDevOps (auditor/standards/code-review/                │
│    soc/security-digest/shannon) · PM Workflows (pm-* + _pm-shared)                            │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
        │ operate on (via gh / git / multi-gitter / HTTP / MCP), never imported as libraries
        ▼
   the rest of the CareSpace platform — GitHub repos (11), the Oracle backlog, ClickUp, Slack, threat feeds
```

## Data Flow

### Idea → planned → built → merged (end-to-end)
1. **`bmad_oracle`** interviews the CEO → `docs/brief.md` + `docs/prd.md` + epics.
2. Epics → story authoring → `stories-output.md` in `carespace-ai/the-oracle-backlog`.
3. Implementation forks by granularity: **`oracle-pipeline`** (whole project, anchor issue → cumulative PR group), **`the-oracle-story-dev`** (one story → PR per repo), or **`pipeline`** (one bug-tracker issue → one PR).
4. **`oracle-pipeline-lifecycle`** reads group status → merges (FR17) or closes (FR18) via multi-gitter, keyed on the shared `feat/oracle-project-<slug>` branch.

Continuous operational loops run in parallel: **SecDevOps** (`carespace-code-review` per-PR review, `carespace-soc` five-module SOC, `security-digest` daily feed) and **PM** (`pm-*` sprint/standup/backlog/retro sync). Per-system flows + the architecture diagram: [skills/AGENTS.md](./skills/AGENTS.md).

## System Boundaries

| Layer | Owns | Does NOT own |
|-------|------|--------------|
| Repo root | skill catalog, ClaudeHub registry, shared recipes/docs, conventions | any product code |
| `skills/` | the six skill systems | the external services/repos they drive |
| Each skill | one job + its triggers | libraries (skills are prompt-first, some with helper scripts) |

## Dependency Direction

```
maestro-skills  →  external tools & CareSpace services
   (gh, git, multi-gitter, serena/code-graph-mcp, ClickUp, Slack, threat feeds, docker, claude)
```
**Rule**: dependencies point outward. Skills consume external CLIs/APIs/MCPs; workflow-to-workflow handoffs happen via authored artifacts (brief/PRD, `stories-output.md`, PR groups), not live imports. Two internal shared nodes are depended-upon: `_pm-shared/context.sh` (Slack/ID config, used by PM *and* security skills) and `carespace-security-standards` (shared HIPAA/OWASP rules). Nothing in the platform depends on this repo at runtime; it is automation tooling invoked by ClaudeHub.

## App Integration

How this repo's skills touch the rest of the CareSpace multi-repo, HIPAA-regulated platform:

| Skill(s) | Talks to | Mechanism | Auth |
|----------|----------|-----------|------|
| `oracle-pipeline` (+lifecycle) · `the-oracle-story-dev` | any `carespace-ai` repo + `the-oracle-backlog` | `gh` + `git` + `multi-gitter` | `GITHUB_TOKEN` |
| `pipeline` | one of 11 product repos (from issue `Repository`) | `gh` + `git` | `GITHUB_TOKEN` |
| `oracle-pipeline` | serena / code-graph-mcp | MCP (code navigation/indexing) | local |
| `carespace-code-review` · `carespace-soc` · `security-digest` | GitHub PRs/issues; NVD/CISA KEV/OSV/GH Advisories/npm/JFrog/HN; Slack | `gh` + HTTPS + Slack Web API | `GITHUB_TOKEN`, Slack bot token |
| `shannon` | target web app/API + its source repo | Docker-run pentester | `ANTHROPIC_API_KEY` |
| `pm-*` | ClickUp, Slack, GitHub | REST + `gh` | ClickUp token, Slack bot token, `GITHUB_TOKEN` |
| `carespace-ai/infra` GH Actions (when present) | invokes `oracle-pipeline-lifecycle` | webhook → ClaudeHub | platform |

### PHI / auth boundaries (documented from code only; not a compliance attestation)
- **No skill reads or writes patient/clinical PHI directly.** They operate on source code, GitHub issues/PRs, planning docs, sprint tasks, and security telemetry. The SecDevOps skills document CareSpace as a HIPAA platform (computer-vision PHI: 553+ body landmarks, health assessments, body-scan imagery) and audit *for* PHI-handling risks, but this repo builds/audits *for* the platform, not on patient data.
- **HIPAA awareness is a review concern, not a data path.** `carespace-security-*` and `pipeline`'s `CARESPACE_CONTEXT.md` carry HIPAA rules so agents flag PHI-touching code (Profile, Client, Evaluation, Survey, body-scan) — the skills themselves never touch that data.
- **Slack egress is guarded.** PM + security skills post ONLY to `_pm-shared` allow-listed channels and FAIL rather than substitute; whether any posted finding/digest contains sensitive material is **unverified** here and is the operator's responsibility.
- **Secrets** (`GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, ClickUp/Slack tokens) come from the environment, never committed (`.gitignore` excludes `.env`). Cross-repo/service calls are one-directional (skills → services); no service calls back into these skills.

## Related Context

- [skills](./skills/AGENTS.md) — the six skill systems, with per-system architecture, data flows, and integration contracts
- `CLAUDE.md` — human-facing skill index, flagship (oracle-pipeline), skill conventions, required secrets
- `SUBAGENT-PATTERNS.md` — canonical parallelization patterns for fan-out
- `shared/helpers.md` — named reusable recipes referenced by skills
- `docs/multi-repo-tools.md` — why multi-gitter (lifecycle) vs hand-rolled loop (implementation)
