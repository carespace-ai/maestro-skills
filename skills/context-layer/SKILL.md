---
name: context-layer
description: Auto-regenerate a repository's Context Layer (hierarchical AGENTS.md + CLAUDE.md nodes) whenever its default branch changes, and open/update one idempotent docs-only PR. Triggered by a GitHub push webhook via Maestro. Trigger keywords context layer, AGENTS.md, regenerate docs, push webhook, default branch changed.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, TodoWrite
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

## STEP 2 — Regenerate the Context Layer (use the bundled tooling)

Use the **same** Context Layer tooling every repo received during the rollout — it
is bundled with this skill under `tooling/` (the `context-layer-coordinator`,
`context-layer-capture`, `context-layer-synthesis` agents + the `context-layer` /
`add-rule` skills). Do **not** hand-roll the format — install the tooling into the
cloned repo and run it.

1. **Install the tooling** into the cloned repo's `.claude/` (also commits it, so
   the layer is self-maintaining — exactly like the initial rollout):
   ```bash
   SKILL_DIR="$HOME/.claude/skills/context-layer"
   [ -d "$SKILL_DIR/tooling" ] || SKILL_DIR="$(dirname "$(find "$HOME/.claude/skills" /app -name should-run.sh -path '*context-layer*' 2>/dev/null | head -1)")/.."
   bash "$SKILL_DIR/tooling/install.sh" "$PWD"
   ```
   This drops `context-layer-{coordinator,capture,synthesis}.md` into
   `.claude/agents/` and `context-layer.md` + `add-rule.md` into `.claude/skills/`,
   scaffolds `.context-layer/manifest.json`, and gitignores `.context-layer/`.

2. **Build the layer yourself, INLINE, following the installed agent specs as the
   format contract.** You are already running as a headless Claude agent, so do
   the coordinator's job directly rather than spawning sub-agents (sub-agent
   fan-out inside a headless run is unreliable and adds nothing here — the output
   is equivalent). Read the three specs you just installed —
   `.claude/agents/context-layer-coordinator.md` (discovery),
   `context-layer-capture.md` (leaf node format), and
   `context-layer-synthesis.md` (parent/root format) — and apply them yourself:
   - **Discover — enumerate EVERY module, then cover ALL that hold real logic.**
     First list every candidate unit: for a monorepo, each app/package; otherwise
     every top-level source dir (e.g. `src/*`, `lib/*`, `packages/*`, `cmd/*`).
     A unit gets a leaf node **unless** it is purely UI/asset/type-only/DTO/
     generated/test/config with no behavior. **There is NO cap on node count** —
     coverage must be COMPLETE. A 30-module repo gets ~30 nodes, not 7. Do not
     stop at the "important-looking" or cross-cutting/infra dirs; the domain/
     business-logic modules are the ones that matter most and must each get a node.
     If a repo has many tiny sibling modules, you MAY group them under one shared
     parent node — but never silently drop a module with real logic.
   - **Capture**: for each system, read its real source (+ grep who-imports-what)
     and write `<system>/AGENTS.md` in the capture.md leaf format (Scope,
     Dependencies BOTH directions, Integration Points, Lifecycle, Ownership,
     State, Key Invariants, Patterns, Anti-patterns; ≤~2000 tokens; do not invent).
   - **Synthesize**: write the parent/root `AGENTS.md` nodes per synthesis.md
     (System Architecture ASCII, Data Flow, boundaries, dependency direction,
     downlinks) and deduplicate shared conventions to the least common ancestor.
   - Create every `CLAUDE.md → AGENTS.md` symlink (`ln -s AGENTS.md CLAUDE.md`).
   - **Completeness self-check (required).** Before STEP 3, list the repo's real
     source dirs and confirm each is either covered by a leaf node or intentionally
     excluded (pure UI/asset/type/generated/test/config). Any real-logic module
     without a node is a bug — go back and capture it. Print the coverage as
     `covered=<n>/<total> modules` and name anything deliberately skipped + why.

   Follow those specs **exactly** — they are the source of truth for the node
   format. **Preserve** any pre-existing user-authored `AGENTS.md`/`CLAUDE.md`
   (never clobber hand-written root docs — add alongside). Since this is a HIPAA
   healthcare platform, the root node's **App Integration** section should note how
   the repo connects to the rest of the CareSpace platform and any **PHI/auth
   boundary** the code shows (code-observed only; mark uncertain facts "unverified").

   (The installed `.claude/agents/` + `.claude/skills/` files ship in the PR too,
   so a human later running "Build context layer" in-repo gets the real tooling.)

   For very large repos (e.g. carespace-ui, carespace-sdk) sampling applies to the
   files **inside** a module — read the entry/module/service/repository files, not
   every file — to stay within budget. It does **NOT** reduce the number of
   modules covered: every real-logic module still gets its own node. Trade depth
   per node for breadth, never breadth for a shorter run.

## STEP 3 — Idempotent docs-only PR (reuse the existing Context Layer PR)

**Do NOT blindly open a new PR.** First look for an ALREADY-OPEN context-layer PR
and reuse its branch, so a repo never accumulates duplicate context-layer PRs
(e.g. an initial rollout `docs/<n>-context-layer` PR + a fresh one). Prefer the
skill's own bot branch `claude/context-layer` if it exists; otherwise reuse any
open context-layer PR's branch; otherwise fall back to `claude/context-layer`.

```bash
# Discover open context-layer PR branches (rollout docs/<n>-context-layer OR claude/context-layer)
BRANCHES=$(gh pr list --repo "$REPO_FULL" --state open --json headRefName \
  -q '.[] | select(.headRefName | test("context-layer")) | .headRefName' 2>/dev/null)
if printf '%s\n' "$BRANCHES" | grep -qx "claude/context-layer"; then
  BRANCH="claude/context-layer"
else
  BRANCH=$(printf '%s\n' "$BRANCHES" | head -1)
  BRANCH="${BRANCH:-claude/context-layer}"   # none open → mint the stable bot branch
fi
echo "target branch: $BRANCH"

git checkout -B "$BRANCH" "$BASE_SHA"        # rebuild off the current default-branch tip
git add -A
git commit -m "docs: update context layer (hierarchical agents.md nodes)"   # lowercase subject (commitlint)

# DIFF GUARD — must be docs-only, else abort without pushing:
DRIFT=$(git diff --name-only "$BASE_SHA"..HEAD | grep -vE '(^|/)AGENTS\.md$|(^|/)CLAUDE\.md$|^\.claude/|^\.gitignore$' || true)
[ -n "$DRIFT" ] && { echo "ABORT: non-docs drift:"; echo "$DRIFT"; exit 1; }

git push -f origin "$BRANCH"                  # force-update: updates the existing PR in place
```

Then **open a PR only if the chosen branch has no open PR yet** (when reusing an
existing branch, the force-push above already updated its PR — do nothing more):

```bash
gh pr view "$BRANCH" --repo "$REPO_FULL" --json state -q .state 2>/dev/null \
  || gh pr create --repo "$REPO_FULL" --base "$DEFAULT_BRANCH" --head "$BRANCH" \
       --title "docs: update Context Layer (hierarchical AGENTS.md)" \
       --body "Automated Context Layer refresh after a change to \`$DEFAULT_BRANCH\`. Docs-only (AGENTS.md + CLAUDE.md nodes); regenerated by the Maestro \`context-layer\` skill. Safe to review & merge."
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
