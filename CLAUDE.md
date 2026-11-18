# Maestro Skills

Claude skills for the Oracle / Maestro autonomous development pipeline,
plus CareSpace SecDevOps and PM workflows.

## Layout

```
maestro-skills/
├── CLAUDE.md                    # this file (skill index, conventions)
├── SUBAGENT-PATTERNS.md         # canonical parallelization patterns
├── shared/
│   └── helpers.md               # named recipes referenced by skills
└── skills/
    ├── oracle-pipeline/         # autonomous BMAD developer (multi-repo)
    ├── carespace-*/             # SecDevOps audit + review skills
    ├── pm-*/                    # PM workflows (sprint, retro, triage, ...)
    └── _pm-shared/              # PM shared assets
```

## Flagship: oracle-pipeline

Implements the BMAD `developer` role with multi-repo orchestration. Takes
a planned BMAD project (epics + stories already authored) and drives every
story to merge-ready (code → tests → coverage ≥ 80% → lint → review → commit
→ PR group).

Trigger: anchor issue with `bmad` + `maestro-ready`, or
`CLAUDEHUB_INPUT_KWARGS.project_slug`.

See [skills/oracle-pipeline/SKILL.md](skills/oracle-pipeline/SKILL.md).

## Skill Conventions

All skills here follow a consistent structure (modeled on
`aj-geddes/claude-code-bmad-skills`):

```
<skill-name>/
├── SKILL.md           # entry point — frontmatter + capabilities + scripts
├── REFERENCE.md       # deep mechanics, lazy-loaded
├── scripts/           # executable bash/python — bash NEVER lives in markdown
├── templates/         # *.template.md, *.template.yaml — placeholders {{var}}
└── resources/         # checklists, standards, opt-in deep context
```

### Frontmatter
```yaml
---
name: <skill-name>
description: <one-line + trigger keywords>
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, TodoWrite, Task
---
```

### Token efficiency rules
- Bash that runs the same way every time → `scripts/*.sh` (never inline in SKILL.md)
- Detail-level mechanics → `REFERENCE.md` (lazy-load on demand)
- Org-specific context → `resources/` (opt-in)
- Never re-read files already in context — pass via env / files
- Use Serena (`find_symbol`, `get_file_outline`) before bulk Read on large repos

### Subagent / parallelization
See top-level [SUBAGENT-PATTERNS.md](SUBAGENT-PATTERNS.md). Use `Task` with
`isolation: "worktree"` and `run_in_background: true` for independent fan-out.
Bundle related small tasks into one agent — don't spawn for trivial work.

## Required Secrets / Tools

| Var / Tool | Used by |
|------------|---------|
| `GITHUB_TOKEN` | gh CLI auth, PR ops |
| `TARGET_ORG` | repo discovery (default `carespace-ai`) |
| `gh`, `jq`, `git`, `python3`, `npx`, `claude` | always |
| `serena`, `code-graph-mcp` | oracle-pipeline (large-codebase nav) |
| `COVERAGE_THRESHOLD` | optional override (default 80) |
| `NOTIFICATION_WEBHOOK_URL` | optional pipeline-complete ping |
| `STRAPI_HOST`, `STRAPI_ADMIN_TOKEN`, `STRAPI_READ_TOKEN` | carespace-content-manager (Strapi base URL, Admin Token for MCP reads/writes, read-only API Token for REST) |
