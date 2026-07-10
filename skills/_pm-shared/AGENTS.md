# PM Workflows (ClickUp × Slack × GitHub sprint automation)

> The project-management system: six autonomous, idempotent skills that keep sprints, standups, backlog, and retros in sync across ClickUp, Slack, and GitHub — all reading a single shared config (`_pm-shared/context.sh`). Owns *sprint coordination*; owns no product code.

This node lives in the shared-config hub `_pm-shared/` and covers it plus six sibling
skill directories: `pm-backlog-triage/`, `pm-daily-pulse/`, `pm-huddle-notes/`,
`pm-retrospective/`, `pm-sprint-planner/`, `pm-status-sync/`. Each is a `SKILL.md`
orchestrating numbered `steps/*.md` shards (data staged in `/tmp` files, no bash inline).

## Scope

**Owns**:
- `_pm-shared/context.sh` — **single source of truth**: ClickUp workspace/space/folder/field IDs, GitHub org, and the Slack allow-list. Sourced by every PM skill (and by `carespace-code-review`/`carespace-soc`).
- `pm-backlog-triage` — import GH issues → ClickUp, dedupe, normalize priority, estimate SP, health report to Slack.
- `pm-daily-pulse` — daily standup digest (read-only on ClickUp) to `$SLACK_STANDUP`.
- `pm-sprint-planner` — capacity/mix validation, move tasks into the active sprint, post plan (hard SP/task cap).
- `pm-retrospective` — velocity calc, move carryovers to candidates, retro summary (only if sprint past due).
- `pm-status-sync` — "Snoop Dogg" bot: DMs team for structured updates, parses replies, syncs to ClickUp, wall of shame (HITL-gated writes).
- `pm-huddle-notes` — archive Slack huddle-note canvases to the GitHub vault (read-only on Slack).

**Does NOT own**: the security skills that also source its context (`carespace-*`); the CareSpace product; ClickUp/Slack/GitHub themselves.

## Dependencies

### This System Depends On

| System | What's Used | Contract |
|--------|-------------|----------|
| ClickUp API | tasks, sprints, custom fields | IDs come ONLY from `context.sh`; never guessed |
| Slack Web API | digests, DMs, wall of shame | Post ONLY to allow-listed channels; FAIL otherwise |
| `gh` CLI + `git` | GH issue import; huddle-note vault archive | Shell; `GITHUB_TOKEN` |
| `/tmp` files | staged API responses (all skills file-based) | Never dump raw JSON to context |

### Systems That Depend On This

| System | How It's Used |
|--------|---------------|
| `carespace-code-review`, `carespace-soc` | Source `_pm-shared/context.sh` for Slack channel IDs |
| ClaudeHub schedules | Trigger each `pm-*` skill on cadence |
| (nothing internal beyond the above) | pm-* skills are entry points |

## Integration Points

### ← every consumer
**What's received**: `context.sh` exports (`WORKSPACE_ID`, `SPACE_*`, `GITHUB_ORG`, `$SLACK_*`, allow-list). **Expectations**: consumers use these verbatim; the three absolute rules (allow-listed channels only, no guessed IDs, follow steps exactly) are enforced at the top of `context.sh`.

### → Slack / ClickUp / GitHub
**What's passed**: digests, task updates, imported issues, archived canvases. **Contract**: idempotent — each skill uses a sprint-id tag or "already posted today" check to avoid double-processing; writes that mutate team data (status-sync, new tasks/issues) are HITL-gated.

## Initialization & Lifecycle

**Created by**: ClaudeHub schedule / manual trigger per skill. **Lifecycle**: ephemeral per run, fully autonomous, idempotent. **State**: `/tmp` scratch during a run; durable state is ClickUp tasks, Slack messages, and the GitHub vault.

## Ownership

| Thing | Relationship | Notes |
|-------|--------------|-------|
| `context.sh` config | **Owns** | The one place IDs/channels are defined |
| ClickUp sprint state | **Shares** | Planner/retro/status-sync mutate (HITL); pulse/backfill read-only |
| Slack channels | **Borrows** | Only the allow-listed ones |

## State

**Holds**: no cross-run state beyond ClickUp/Slack/vault; `/tmp` files per run. **Mutable**: ClickUp tasks (write skills). **Immutable**: `context.sh` IDs and the allow-list.

## Key Invariants

- **Never** post to a channel outside `SLACK_ALLOWED_CHANNELS` (never `#carespace-team`/`#general`/`#eng-general`) — FAIL, don't substitute.
- **Never** guess/infer ClickUp IDs, field names, or values — use `context.sh` only.
- **Must** follow each skill's `steps/*.md` exactly (no skip/reorder); mutating team data requires HITL approval; runs are idempotent (sprint-id tag / once-per-day guard).

## Patterns

```bash
# Step 0 of every PM skill: load the single source of truth
source ~/.claude/skills/_pm-shared/context.sh
```

## Anti-patterns

```text
# ❌ Don't fall back to a different Slack channel or invent a ClickUp field ID
# ✅ Do fail loudly and report the missing channel/ID
```
