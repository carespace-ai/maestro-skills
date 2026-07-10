# CareSpace SecDevOps (security audit, review, SOC, digest, pentest)

> The security system: HIPAA/OWASP-aware detection, PR security review, continuous SOC operations, a daily threat-intel digest, and an autonomous pentester. Owns *finding and reporting* security risk across the CareSpace platform; owns no product code and applies no fixes.

This node covers six sibling skill directories forming one cohesive security system:
`carespace-security-auditor/`, `carespace-security-standards/`, `carespace-code-review/`,
`carespace-soc/`, `security-digest/`, and the vendored third-party `shannon/`.

## Scope

**Owns**:
- `carespace-security-auditor` — the detection engine: audits PR diffs by file type (TS/React, NestJS/Prisma, Flutter, Azure) for HIPAA/OWASP issues. Every finding has PHI implications.
- `carespace-security-standards` — **reference/abstract** skill (do not invoke directly): the canonical HIPAA-in-code/storage/transit, OWASP-in-CareSpace-context, and Azure rules the other skills reason against.
- `carespace-code-review` — orchestrator: discover open PRs → threat-intel/CVE map → per-PR security + quality review → post PR comment → Slack summary to `#pm-engineering` (mandatory Step 6).
- `carespace-soc` — five-module SOC: Detect (secret + CVE scan) → Audit (HIPAA/SOC2 gaps) → Triage → Evidence (compliance artifacts) → Respond (GitHub issues + Slack digest).
- `security-digest` — daily read-only intel digest across 7 feeds (NVD, CISA KEV, GH Advisories, OSV, npm audit, JFrog, HN); tags CareSpace-stack matches; posts once/day to `#ops-general`.
- `shannon` — vendored KeygraphHQ autonomous white-box pentester (Docker, AGPL); proves vulns via real exploits.

**Does NOT own**: fixing vulnerabilities (findings only); the PM Slack channel config it borrows (`_pm-shared`); product source in target repos.

## Dependencies

### This System Depends On

| System | What's Used | Contract |
|--------|-------------|----------|
| `_pm-shared/context.sh` | Slack channel IDs / allowed-channel guard | Sourced by `carespace-code-review`, `carespace-soc`; FAIL if channel missing — never substitute |
| `carespace-security-standards` | shared HIPAA/OWASP/Azure rules | Conceptual reference for auditor/code-review/soc |
| `gh` CLI + `git` | PR/issue read, comment, issue file | Shell; `GITHUB_TOKEN` |
| Threat-intel feeds (NVD, CISA KEV, OSV, GH Advisories, npm audit, JFrog, HN) | CVE/vuln data | HTTPS, read-only; responses cached to `/tmp` files, never dumped to context |
| Slack Web API | post findings/digests | Bot token; only to allow-listed channels |
| `docker`, `git`, `ANTHROPIC_API_KEY` | shannon runtime | `scripts/setup-shannon.sh`; AGPL third-party |

### Systems That Depend On This

| System | How It's Used |
|--------|---------------|
| ClaudeHub jobs (`.claudehub.yml`) | `/carespace-code-review`, `/carespace-security-auditor`, `/carespace-security-standards` scheduled/triggered |
| Slack `#pm-engineering` / `#ops-general` | Findings + digest destinations |
| (nothing internal) | Entry-point orchestrators |

## Integration Points

### → GitHub PRs / issues
**What's passed**: PR review comments (findings only — no filler), filed issues for SOC findings. **Contract**: comment findings must match the summary table counts; zero findings → short PASS.

### ← _pm-shared/context.sh
**What's received**: `$SLACK_*` channel IDs + the allow-list. **Expectations**: post ONLY to listed channels; fail loudly otherwise.

## Initialization & Lifecycle

**Created by**: ClaudeHub skill triggers / schedules. **Lifecycle**: ephemeral per run; idempotent (security-digest posts once/day and updates in place). **State**: `/tmp` files hold all API responses; durable output is PR comments, GitHub issues, Slack messages, and (SOC) compliance evidence artifacts.

## Ownership

| Thing | Relationship | Notes |
|-------|--------------|-------|
| Findings / reviews / evidence | **Owns** | Authors; writes to `/tmp/review-{repo}-{n}.md` then batch-posts |
| Security standards rules | **Owns** | `carespace-security-standards` is the source of truth |
| Slack channel config | **Borrows** | From `_pm-shared/context.sh` |
| Target repo code / PRs | **Shares** | Reads diffs; never writes code |

## State

**Holds**: per-run `/tmp` scratch (CVE maps, review drafts, digest data). **Mutable**: batched before posting. **Immutable**: the standards rules and allow-listed channel set.

## Key Invariants

- **Never** post to a Slack channel not in `_pm-shared` allow-list (never `#general`/`#carespace-team`) — FAIL instead of substituting.
- **Never** dump raw feed JSON into context — all API responses go to `/tmp` files.
- **Must**: PR comments contain findings only, and summary-table counts must equal the findings listed; CVE items appear only if the PR touches the vulnerable package/version.
- **Assumes**: all reviewed code may handle PHI — every security issue is treated as HIPAA-relevant.

## Patterns

```bash
# Every PM/security skill loads channel config the same way
source ~/.claude/skills/_pm-shared/context.sh   # exports $SLACK_ENGINEERING, allow-list
```

## Anti-patterns

```text
# ❌ Don't invoke carespace-security-standards directly (it's a reference skill)
# ❌ Don't "helpfully" pick a fallback Slack channel
# ✅ Do fail and report when the target channel is missing
```
