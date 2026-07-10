---
name: context-layer
description: Auto-regenerate a repository's Context Layer (hierarchical AGENTS.md + CLAUDE.md nodes) whenever its default branch changes, and open/update one idempotent docs-only PR. Triggered by a GitHub push webhook via Maestro. Trigger keywords context layer, AGENTS.md, regenerate docs, push webhook, default branch changed.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Context Layer — auto-update on push

**Role:** Keep a repo's **Context Layer** (hierarchical `AGENTS.md` + `CLAUDE.md`
symlink nodes) in sync with its code. When the default branch (`master`/`main`)
changes, regenerate the layer for that repo and open **one idempotent, docs-only
PR** on the bot branch `claude/context-layer`.

This skill is repo-agnostic: it figures out **which repo** from the webhook
payload and clones it itself. One Maestro webhook trigger + this one skill covers
every repo.

## Input

Maestro sets **`$CLAUDEHUB_INPUT_KWARGS`** to the JSON body of the GitHub push
webhook (the trigger's default `input_kwargs` merged with the request body). You
read the repo, ref, sender, and changed files from it. `GITHUB_TOKEN` is present
in the environment (a saved secret) for cloning and PR creation.

## STEP 0 — Guard (decide RUN vs SKIP)

Run the guard and **stop immediately** unless it says `DECISION=RUN`. The script
lives next to this SKILL.md; find it robustly:

```bash
GUARD="$HOME/.claude/skills/context-layer/scripts/should-run.sh"
[ -f "$GUARD" ] || GUARD="$(find "$HOME/.claude/skills" /app -name should-run.sh -path '*context-layer*' 2>/dev/null | head -1)"
bash "$GUARD"
```

The guard emits `REPO_FULL`, `DEFAULT_BRANCH`, `CLONE_URL`, and a final
`DECISION=RUN|SKIP` (+ `REASON`). It returns **SKIP** for:
- pushes that are **not** to the default branch,
- pushes authored by automation (`*[bot]`, `*maestro*`, `*claudehub*`,
  `*context-layer*`) — the **loop guard**,
- **docs-only** pushes (only `AGENTS.md` / `CLAUDE.md` / `.claude/**` changed) —
  the second **loop guard** (this is the context layer's own merge landing).

If `DECISION=SKIP`: print the reason, do nothing else, and finish the run
successfully. **Never** proceed past a SKIP — that is what prevents infinite
regeneration loops.

## STEP 1 — Clone the target repo

```bash
REPO_FULL=<from guard>          # e.g. carespace-ai/carespace-ui
DEFAULT_BRANCH=<from guard>
WORK=/tmp/ctx-$RANDOM && mkdir -p "$WORK" && cd "$WORK"
git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_FULL}.git" repo
cd repo
git fetch --depth 1 origin "$DEFAULT_BRANCH"
BASE_SHA=$(git rev-parse HEAD)
git config user.name  "maestro-context-layer[bot]"
git config user.email "context-layer@carespace.ai"
```
For very large repos, do **not** read every file — sample strategically.

## STEP 2 — Regenerate the Context Layer

Produce a hierarchy of `AGENTS.md` nodes, each with a sibling `CLAUDE.md` symlink
(`ln -s AGENTS.md CLAUDE.md`). **Preserve** any pre-existing user-authored
`AGENTS.md`/`CLAUDE.md` (never clobber hand-written root docs — add alongside).

**Discover systems**: cohesive units with real logic (one job, clear boundaries).
Skip pure UI/assets/type-only/generated/test dirs. For a monorepo, treat each
app/package as a container of systems. Aim for ~4–10 leaf nodes.

**Leaf node** (`<system>/AGENTS.md`) — fill every section:
`# <System>` · one-line summary · `## Scope` (Owns / Does NOT own) ·
`## Dependencies` with **both** `This System Depends On` and `Systems That Depend
On This` tables · `## Integration Points` · `## Initialization & Lifecycle` ·
`## Ownership` (owns/borrows/shares) · `## State` · `## Key Invariants` (2–3, or
"none identified") · `## Patterns` · `## Anti-patterns`. Keep ≤ ~2000 tokens;
prefer tables. Base every claim on real source — do not invent; mark uncertain
facts "unverified".

**Parent / root nodes** (synthesis): `## System Architecture` (ASCII diagram) ·
`## Data Flow` (≥1 flow) · `## System Boundaries` · `## Dependency Direction` ·
`## Related Context` (downlinks to children). The **root** additionally gets an
`## App Integration` section: how this repo talks to the rest of the CareSpace
multirepo platform (REST/CMS/auth/queues) and any **PHI/HIPAA** boundary it
touches (code-observed only). Deduplicate shared conventions up to the least
common ancestor.

If the repo already ships context-layer agents under `.claude/agents/`, follow
their leaf/parent/root formats exactly. (This is a HIPAA healthcare platform —
note PHI/auth boundaries where the code shows them.)

## STEP 3 — Idempotent docs-only PR

```bash
git checkout -B claude/context-layer "$BASE_SHA"   # bot branch: exempt from branch-name/PR-link validators
git add -A
git commit -m "docs: update context layer (hierarchical agents.md nodes)"   # lowercase subject (commitlint)

# DIFF GUARD — must be docs-only, else abort without pushing:
DRIFT=$(git diff --name-only "$BASE_SHA"..HEAD | grep -vE '(^|/)AGENTS\.md$|(^|/)CLAUDE\.md$|^\.claude/|^\.gitignore$' || true)
[ -n "$DRIFT" ] && { echo "ABORT: non-docs drift:"; echo "$DRIFT"; exit 1; }

git push -f origin claude/context-layer     # force-update: idempotent, reuses the same branch/PR
```

Then **open the PR only if one is not already open** (idempotent — the force-push
above updates an existing open PR automatically):

```bash
gh pr view claude/context-layer --repo "$REPO_FULL" --json state -q .state 2>/dev/null \
  || gh pr create --repo "$REPO_FULL" --base "$DEFAULT_BRANCH" --head claude/context-layer \
       --title "docs: update Context Layer (hierarchical AGENTS.md)" \
       --body "Automated Context Layer refresh after a change to \`$DEFAULT_BRANCH\`. Docs-only (AGENTS.md + CLAUDE.md nodes); regenerated by the Maestro \`context-layer\` skill. Bot branch — safe to review & merge."
```

## STEP 4 — Report

Print a compact summary: repo, whether it ran or skipped (+ reason), node count,
the PR URL (or "updated existing PR"), and any required-check caveat. Note if the
repo enforces CareSpace's develop-first governance (a `check-sibling` on master
PRs may need a human to complete the merge via the develop sibling) — do NOT open
sibling PRs from this skill.

## Guarantees / invariants

- **Never** produces a non-docs diff (DIFF GUARD aborts).
- **Never** loops: SKIP on automation authors and docs-only pushes.
- **Idempotent**: one long-lived `claude/context-layer` branch/PR per repo; a new
  push force-updates it instead of stacking PRs.
- **Non-destructive**: preserves user-authored AGENTS.md/CLAUDE.md content.
