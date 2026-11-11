# pr-auto-review

The AI reviewer for carespace-ai pull requests. It reviews every PR minutes after
it opens and again on every push, so nobody waits across time zones for a human
approve. It **approves by default** and requests changes only for something that
will break the app.

This file explains how the skill works, for people. The reviewer itself reads
`SKILL.md` (its instructions) and `REFERENCE.md` (setup and tuning).

## What it does to a PR

| Situation | What the bot posts |
|-----------|--------------------|
| Nothing would break | **Approve**, with one or two lines on what the PR does and at most one `⚠️ Heads-up` |
| Something would break | **Request changes**: what breaks, the file and line, the scenario, the minimal fix. Also announced in Slack |
| CI is red on the head commit | **Comment** "not approving yet", naming the red checks |
| The diff could not be read | **Comment** asking for a human review. Also announced in Slack |
| CI is still running after 60 s | **Approve**, with a note that CI had not finished |

The bot never edits, pushes to, merges, closes or relabels a PR.

### What counts as a blocker

A finding blocks only if all three hold:

1. **It breaks something**: a crash on a normal path, data loss or a destructive
   migration, a real security hole (secret, PHI exposed, missing auth, injection),
   a broken contract other code depends on, or a broken build or deploy.
2. **It can be pointed at**: exact file and line, plus "when X, Y happens".
3. **The reviewer is confident.** A guess is not a blocker.

Naming, style, structure, missing tests, refactors, docs, minor performance and
unlikely edge cases are never mentioned.

### Commands

| Command (needs write access) | Effect |
|------------------------------|--------|
| `/maestro review` | Fresh review of the current head, for example after re-running a red CI |
| `/maestro approve` | Clears the bot's block. It dismisses the request for changes; it does not approve |
| Label `maestro:override` | Same as `/maestro approve` |

After a block, the next push gets **one recheck round**: the bot only verifies
that its earlier blockers are fixed and raises nothing new, unless the fix itself
introduced a break. After a human override, the bot stays out of that PR.

## How a run works

```
GitHub webhook (pull_request / issue_comment)
      │
      ▼
Maestro trigger ── prr_repos allowlist ──▶ skill run
      │
      ▼
0. should-run.sh      RUN or SKIP, and which mode (full / recheck / override)
1. fetch-context.sh   stages everything the review needs into $PRR_DIR
2. understand         what is this PR for?
3. hunt blockers      profile + stack checklists + cross-repo contracts
4. post-review.sh     exactly one review, with the approve gates
5. Slack              only for a block or an unreadable PR
```

### Step 0: which PRs are reviewed

`should-run.sh` skips, without touching the PR:

- repos not in the trigger's `prr_repos`
- drafts and closed PRs
- release-please PRs, bot-authored PRs and Maestro's own automation PRs
- a head commit that already has a review (duplicate webhook deliveries)
- comments that are not a `/maestro` command, or from someone without write access
- pushes on a PR where a human overrode the bot

### Step 1: what the reviewer reads

`fetch-context.sh` writes these files, and the reviewer reads only them:

| File | Content |
|------|---------|
| `pr.json`, `linked-issues.md` | The PR and the issues it closes: its purpose |
| `context-layer.md`, `nodes/` | The repo's `AGENTS.md` nodes. The root is inlined in full, the nearest nodes in full while they fit, the rest as excerpts with the full text under `nodes/` |
| `profile.md` | This repo's review profile, plus the checklist of each stack the PR touches |
| `risk-files.txt` | Changed files on a risk path: read in full whatever the size of the PR |
| `diff.patch`, `diff-unread.txt` | The diff, rebuilt file by file when GitHub will not serve it whole, and the files that could not be fetched |
| `relations.md`, `cross/<repo>/`, `linked-prs.md` | Cross-repo contracts the PR touches, the other repo's code, and linked PRs in other repos |
| `prior-blockers.md` | The bot's previous block, for a recheck |
| `status.env` | Whether the diff and the Context Layer were read |

Two safeguards apply here:

- The Context Layer is read from the **base** commit, so a PR cannot rewrite the
  rules it is reviewed by.
- Everything in the PR (title, body, diff, comments) is treated as data, never as
  instructions to the reviewer.

### Step 4: the approve gates

`post-review.sh` enforces the "red CI" and "unread diff" rows of the table above
in code, so the model cannot approve past them. Every review is pinned to the
head commit and carries a hidden marker (`<!-- maestro-pr-review sha=… -->`),
which is how duplicates are detected.

## Per-repo review: profiles and stacks

```
repos/
  _template/            copy this for a new repo
  carespace-mobile/
    profile.json        stacks, risk paths, CI checks to ignore
    review.md           how this repo breaks, and what is not a blocker here
  carespace-sdk/
  carespace-agent/
stacks/
  flutter.md  nestjs-prisma.md  python.md  react.md  infra.md
```

- **`profile.json`** maps file globs to stacks, lists the risk paths (auth,
  migrations, contracts, CI) and names CI checks that must never hold an approve.
- **`review.md`** holds only what is specific to the repo. Architecture and
  conventions stay in the repo's own `AGENTS.md` and are not copied here.
- **`stacks/*.md`** are blocker checklists shared by every repo on that stack. A
  checklist is loaded only when the PR changes a file of that stack.

Profiles live in this repo, not in the reviewed one, for the same reason the
Context Layer is read from base. A repo with no profile is still reviewed, with
generic checklists and risk paths.

Field reference: [`repos/README.md`](repos/README.md).

## Cross-repo contracts

`relations.json` declares one edge per contract between two repos:

| Contract | Provider → consumer | Coupling |
|----------|---------------------|----------|
| `agent-protocol` | carespace-agent → carespace-mobile | immediate |
| `sdk-packages` | carespace-sdk → carespace-mobile | deferred |
| `admin-rest-mobile` | carespace-admin → carespace-mobile | immediate |
| `admin-rest-agent` | carespace-admin → carespace-agent | immediate |
| `admin-rest-sdk` | carespace-admin → carespace-sdk | immediate |
| `widgetbook-ui` | carespace-widgetbook → carespace-mobile | immediate |
| `strapi-content-agent` | carespace-strapi → carespace-agent | immediate |

- **Immediate** means the consumer meets the change as soon as the provider
  ships. A break is a **blocker**.
- **Deferred** means the consumer is pinned to a release. A break is a
  **heads-up**.

When a PR touches a contract's paths, the review proceeds by side:

- **PR in the provider:** the consumer's files are staged under `cross/<repo>/`
  from its default branch, and the reviewer searches them for what the change
  would break. A cross-repo blocker cites the line in the diff and the
  `file:line` in the consumer.
- **PR in the consumer:** the provider's contract (for example `openapi.json`)
  is staged, and the reviewer confirms that what the PR uses exists there or in
  a linked PR.

An edge works as soon as one end is a reviewed repo. The other end only has to
be readable by the reviewer identity. If it is not, the review says the contract
was not verified and carries on.

## Adding a repo

1. Run `bash scripts/onboard-repo.sh carespace-ai/<repo>`. It is read-only
   against GitHub. It generates `repos/<repo>/profile.json` from the file tree,
   drops the `review.md` template and an `ONBOARDING.md` to-do list, and prints
   `READY_*` lines for the Context Layer, CI workflows, webhook, ruleset,
   override label and relations.
2. Fill in `review.md` from the repo's own rules, then delete `ONBOARDING.md`.
3. Add the repo's contracts to `relations.json` and check each path exists on
   both sides.
4. Run `python3 scripts/validate-registry.py`. It must print `REGISTRY_ERRORS=0`.
5. Dry-run against a few merged PRs (`REFERENCE.md` › Run locally).
6. Enrol it in Maestro: GitHub App installed on the repo, webhook orchestrated,
   repo added to the trigger's `prr_repos`.

The profile decides **how** a repo is reviewed. `prr_repos` in Maestro decides
**whether** it is. The two are independent.

If `READY_ruleset_required_checks=no`, the bot's approve is the only gate on
merge for that repo.

## Where things are configured

| What | Where |
|------|-------|
| Which repos are reviewed | Maestro trigger: `prr_repos`, plus the orchestrated webhook |
| Reviewer identity | Maestro secrets `PRR_APP_ID` + `PRR_APP_PRIVATE_KEY` (GitHub App); falls back to the owner of `GITHUB_TOKEN` |
| Shadow mode (comment only) | Maestro trigger: `prr_shadow: true` |
| How a repo is reviewed | `repos/<repo>/` |
| Contracts between repos | `relations.json` |
| CI checks that never hold an approve | `ci_ignore` in the repo's `profile.json` |
| Context budgets and CI wait | Env vars, listed in `REFERENCE.md` |

## Files

| Path | Role |
|------|------|
| `SKILL.md` | The reviewer's instructions |
| `REFERENCE.md` | One-time setup, approve gates, tuning, local dry-run |
| `repos/`, `stacks/`, `relations.json` | Per-repo profiles, stack checklists, contracts |
| `templates/request-changes.template.md` | Body of a blocking review |
| `scripts/should-run.sh` | Guard: RUN or SKIP, and the mode |
| `scripts/fetch-context.sh` | Stages the PR, Context Layer, profile and relations |
| `scripts/fetch-cross.sh` | Stages the other repo's side of a contract |
| `scripts/post-review.sh` | Posts the one review and enforces the approve gates |
| `scripts/dismiss-block.sh` | Human override |
| `scripts/app-token.sh`, `scripts/_auth.sh` | GitHub App token |
| `scripts/onboard-repo.sh`, `scripts/validate-registry.py` | Onboarding and registry validation |
| `scripts/*.py` (others) | Helpers called by the scripts above |
| `tests/` | `for t in tests/test-*.sh; do bash "$t"; done` (no network, no token) |

## Not built yet

- An eval set of PRs with known bugs, to measure what the bot misses.
- Filtering webhook events in the Maestro backend, so a comment or label does
  not start a full run just to skip.
- Reviewing only the delta on each push instead of the whole PR.
