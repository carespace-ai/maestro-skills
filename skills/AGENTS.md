# skills/ — Maestro / Oracle Skill Systems

> The catalog of Claude skills for the Oracle / Maestro autonomous development pipeline, plus CareSpace SecDevOps and PM automation. Each skill is a self-contained directory (a front-mattered `SKILL.md`, optionally `REFERENCE.md`, `scripts/`, `steps/`, `templates/`, `resources/`); ClaudeHub invokes them by trigger. Grouped into six functional systems.

## System Architecture

```
┌────────────────────────── skills/ (Maestro / Oracle skills) ───────────────────────────┐
│                                                                                         │
│  PLANNING              AUTONOMOUS DELIVERY                                               │
│  ┌───────────────┐     ┌───────────────────────────────────────────────────────────┐   │
│  │ bmad_oracle   │────▶│ oracle-pipeline (+ lifecycle)  project-wide, PR group       │   │
│  │ brief → PRD   │     │ the-oracle-story-dev           single story, PR per repo    │   │
│  │ → epics       │     │ pipeline (gstack)              single issue → one PR        │   │
│  └───────────────┘     └───────────────────────┬───────────────────────────────────┘   │
│        docs/*.md                                │ gh / git / multi-gitter                │
│                                                 ▼                                        │
│                                        GitHub PRs across 11 carespace-ai repos           │
│                                                                                         │
│  SECDEVOPS                                        PM WORKFLOWS                            │
│  ┌────────────────────────────────────────┐      ┌───────────────────────────────────┐  │
│  │ carespace-security-auditor / standards │      │ pm-backlog-triage · daily-pulse   │  │
│  │ carespace-code-review · carespace-soc  │◀────▶│ sprint-planner · retrospective    │  │
│  │ security-digest · shannon (pentest)    │ ctx  │ status-sync · huddle-notes        │  │
│  └────────────────────────────────────────┘      │ ← _pm-shared/context.sh (config)  │  │
│         findings → PR comments / issues / Slack   └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
   depends on external tools/APIs (gh, git, multi-gitter, ClickUp, Slack, feeds) — never imported as libraries
```

## Data Flow

### Idea → planned → built → merged (the autonomous loop)
1. **`bmad_oracle`** interviews the CEO → `docs/brief.md` + `docs/prd.md` + epics.
2. Epics → story authoring → `stories-output.md` in `the-oracle-backlog`.
3. **`oracle-pipeline`** (whole project, anchor issue) or **`the-oracle-story-dev`** (one story) or **`pipeline`** (one bug-tracker issue) implements → opens the PR group.
4. **`oracle-pipeline-lifecycle`** reads group status, then merges (FR17) or closes (FR18) via multi-gitter.

### Continuous security + PM (parallel operational loops)
- **SecDevOps**: `carespace-code-review` reviews each open PR (CVE map + HIPAA/OWASP) → PR comment → Slack; `carespace-soc` runs Detect→Audit→Triage→Evidence→Respond; `security-digest` posts a daily feed roundup.
- **PM**: `pm-*` skills sync ClickUp ⇄ Slack ⇄ GitHub for sprints/standups/backlog/retros, all reading `_pm-shared/context.sh`.

## System Boundaries

| System | Owns | Does NOT own |
|--------|------|--------------|
| BMAD Oracle | brief/PRD/epic authoring | code, GitHub mutation |
| Oracle Pipeline (+lifecycle) | project-wide multi-repo delivery + PR-group lifecycle | story authoring, single-story/issue dev |
| Oracle Story Dev | one story across its repos_affected | project-wide delivery, merge |
| gstack Pipeline | one issue → one PR (bug-tracker driven) | multi-story orchestration |
| SecDevOps | finding/reporting security risk | fixing it; product code |
| PM Workflows | sprint/backlog/standup coordination | product code |

## Dependency Direction

```
bmad_oracle → (docs/epics) → oracle-pipeline / the-oracle-story-dev / pipeline
                                   │ open PR group
                                   ▼
                          oracle-pipeline-lifecycle (multi-gitter)
_pm-shared/context.sh ──▶ pm-* AND carespace-code-review / carespace-soc  (shared Slack/ID config)
carespace-security-standards ──▶ carespace-security-auditor / code-review / soc  (shared rules)
```
**Rule**: dependencies point outward to external tools/APIs (`gh`, `git`, `multi-gitter`, ClickUp, Slack, threat feeds) or to a shared-config/reference node (`_pm-shared`, `carespace-security-standards`). No skill is imported as a library; handoffs between workflows happen via authored artifacts (docs, backlog files, PR groups), not live calls.

## Integration Contracts

| From | To | What's Passed | Contract |
|------|-----|---------------|----------|
| bmad_oracle | pipelines | epics/PRD (→ stories-output.md) | Artifact handoff, not a live call |
| oracle-pipeline | oracle-pipeline-lifecycle | `BRANCH` + `INVOLVED_REPOS` (phase env) | multi-gitter selects by shared branch name |
| pipeline | target repo | branch + one PR | Repo from issue `Repository` field |
| _pm-shared | pm-* + security skills | `context.sh` exports | Allow-listed channels + fixed IDs only |
| carespace-code-review | Slack `#pm-engineering` | findings summary | Mandatory Step 6; counts must match |

## Shared Conventions

- Every skill is a directory with a front-mattered `SKILL.md`; `description` carries the trigger phrases the loader matches.
- Bash that runs the same way every time lives in `scripts/*.sh` (or numbered `steps/*.md` for PM) — never inline in `SKILL.md` (token efficiency; see `../shared/helpers.md`).
- `REFERENCE.md` and `resources/` are lazy-loaded/opt-in; skills read `SKILL.md` by default (~3k tokens).
- Autonomous skills are idempotent and stage API data in `/tmp` files — never dump raw JSON into context.
- Parallel fan-out uses `Task` with `isolation: "worktree"` + `run_in_background: true` (see `../SUBAGENT-PATTERNS.md`); bundle trivial work, don't over-spawn.
- Secrets come from env (`GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, Slack bot token) — never committed.

## Related Context

- [oracle-pipeline](./oracle-pipeline/AGENTS.md) — project-wide autonomous BMAD developer + PR-group lifecycle
- [the-oracle-story-dev](./the-oracle-story-dev/AGENTS.md) — single-story BMAD dev via multi-gitter
- [pipeline](./pipeline/AGENTS.md) — single-issue gstack sprint (bug-tracker driven)
- [bmad_oracle](./bmad_oracle/AGENTS.md) — CEO product discovery → brief/PRD/epics
- [carespace-security-auditor](./carespace-security-auditor/AGENTS.md) — SecDevOps: auditor · standards · code-review · soc · security-digest · shannon
- [_pm-shared](./_pm-shared/AGENTS.md) — PM Workflows: backlog · pulse · planner · retro · status-sync · huddle-notes
