# pr-auto-review — reference

Lazy-loaded. Per-stack blocker checklists live in `stacks/`, per-repo review
profiles in `repos/` (see `repos/README.md`). `fetch-context.sh` stages the ones a
PR needs into `$PRR_DIR/profile.md` — you never read `stacks/` or `repos/` directly.

# One-time setup

1. **Reviewer identity — GitHub App (preferred) or PAT.**
   - **App:** a `carespace-ai` GitHub App (no webhook; permissions *Pull requests: write*,
     *Contents: read*, *Issues: read*, *Checks: read*, *Commit statuses: read*, *Metadata:
     read*) installed on the reviewed repos. Save two Maestro secrets: `PRR_APP_ID` and
     `PRR_APP_PRIVATE_KEY` (the `.pem` — raw, `\n`-escaped, or base64 on one line).
     `app-token.sh` mints a 1-hour installation token per run; reviews show as
     `<slug>[bot]`, so **everyone's** PRs get reviewed, including the PAT owner's.
     Repo rulesets count an App's approve when it has write access; Apps can't be
     code owners, so code-owner-required repos still need a human approve.
   - **PAT fallback** (no App secrets): the saved `GITHUB_TOKEN`'s owner is the reviewer,
     resolved via `GET /user`; that account's own PRs are skipped (no self-approval).
   `SLACK_BOT_TOKEN` (escalations) is reused from Maestro's saved secrets either way.
2. **Maestro trigger.** Create a webhook trigger for `pr-auto-review` (same kind as
   `context-layer`'s). Default `input_kwargs` for the shadow week:
   `{"prr_shadow": true, "prr_repos": ["carespace-api"]}`. Remove both keys to go live.
3. **GitHub webhook** — today Maestro's hooks are **per repo** (e.g. carespace-mobile has a
   push-only hook → the context-layer token). Add a second hook per repo, or one org hook
   (`carespace-ai` → Settings → Webhooks, needs an org owner): payload URL
   `https://<maestro>/api/v1/webhooks/<trigger-token>`, content type `application/json`,
   events **Pull requests** + **Issue comments** only. The token URL is the only auth on
   this endpoint (no HMAC) — treat it as a secret.
4. **Label** `maestro:override` in each repo (optional; `/maestro approve` works without it).
   Like the comment, the label only counts when the person adding it has write access.

# Approve gates and tuning

`post-review.sh` never posts an `APPROVE` for a PR that was not read, is red,
touches a human-only path, or moved under the reviewer:

| Situation | What is posted | Way back |
|-----------|----------------|----------|
| `status.env` absent or `DIFF_STATUS=missing` | COMMENT — "could not read this PR's diff" | `/maestro review`, or a human review |
| CI failing on the head commit | COMMENT — "not approving yet", red checks named | push a fix, or re-run CI + `/maestro review` |
| PR changes a `human_paths` file (or the profile could not be resolved) | COMMENT — the review, plus "a human approve is needed" | a human approve |
| PR head is no longer the commit under review | nothing | the newer push's run reviews it |
| CI still running after `PRR_CI_WAIT` s | APPROVE + "CI was still running" note | — |
| CI unreadable (API error) | APPROVE + "could not read CI" note | — |

| Env var | Default | Meaning |
|---------|---------|---------|
| `PRR_CI_WAIT` | `60` | seconds to wait for running checks before posting (keep under the Bash tool timeout) |
| `PRR_CI_IGNORE` | repo profile `ci_ignore` | regex of check / status names that never hold an approve (preview deploys, advisory jobs) |
| `PRR_ROOT_CAP` | `60000` | chars of the root Context Layer node inlined before it is condensed |
| `PRR_CONTEXT_BUDGET` | `60000` | chars of nested nodes inlined in full; the rest are excerpted |
| `PRR_NODE_EXCERPT` | `8000` | chars of priority sections kept per excerpted node |
| `PRR_MAX_NODES` | `12` | Context Layer nodes fetched per PR |

`/maestro review` (write access) re-reviews the current head even when that SHA
already carries a review. `/maestro approve` still only clears a block.

# Run locally against a real PR (no posting)

```bash
export CLAUDEHUB_INPUT_KWARGS="$(gh api repos/carespace-ai/<repo>/pulls/<n> | python3 -c 'import json,sys; pr=json.load(sys.stdin); print(json.dumps({"action":"opened","repository":pr["base"]["repo"],"pull_request":pr}))')"
bash scripts/should-run.sh
bash scripts/fetch-context.sh carespace-ai/<repo> <n> <base_sha>
PRR_DRY_RUN=1 bash scripts/post-review.sh carespace-ai/<repo> <n> <head_sha> APPROVE /tmp/review.md
```

# Tests

`for t in tests/test-*.sh; do bash "$t"; done` — no network, no token needed.
