# pr-auto-review — per-stack blocker checklists

Lazy-loaded. Use only for the stack the diff touches. Every item is a **blocker
candidate** — it still has to pass the three-part test in SKILL.md STEP 3
(breaks something · exact line + scenario · confident). Not on this list → not a blocker.

## NestJS / Prisma (backend APIs)
- New/changed controller route without the guard its siblings use (`@UseGuards`, role/tenant checks) → unauthenticated or cross-tenant access.
- Prisma query that drops the tenant/clinic/patient scoping filter its siblings apply.
- `prisma migrate` that drops/renames a column or table still read by code in this repo or a documented consumer; `NOT NULL` added without default/backfill.
- DTO/response shape change on an endpoint the Context Layer lists as consumed by another app (mobile, web, bots).
- PHI (patient names, DOB, notes, media URLs) written to logs, error messages, analytics or 3rd-party calls.
- `await` missing on a write whose result is relied on; unhandled promise in a request path.
- New required env var read without default and not added to deploy config.

## React / Next.js (web)
- Runtime crash on render: accessing a property of possibly-undefined API data with no guard on a path users hit.
- Hook rule violation (conditional hook) — crashes at runtime.
- API client call shape out of sync with the backend contract changed in the same PR group.
- Secrets/keys in client bundles (`NEXT_PUBLIC_*` holding a server secret).
- `dangerouslySetInnerHTML` with user/patient content.

## Flutter / Dart (carespace-mobile, kiosk)
- Null-check `!` on data that the API can return null → crash.
- `BuildContext` used after `await` without `mounted` check in a navigation/dialog path.
- Platform channel / permission change without the matching Android manifest / iOS Info.plist entry → crash or store rejection.
- Asset or path dependency referenced but not declared in `pubspec.yaml`.
- Breaking change to a model's `fromJson` that the backend still sends in the old shape.

## Python / FastAPI (maestro, workers)
- Route missing the auth dependency its siblings use.
- Alembic migration that is destructive or non-reversible on live data without a backfill.
- Blocking/long work moved into the API process where the Context Layer says it must run in the worker.
- SQL built with f-strings from request input.
- Sync I/O inside `async def` on a hot path that would stall the event loop (only if it clearly would).

## Infra / config
- Workflow/CI change that disables required checks or exposes secrets to PRs from forks.
- Dockerfile/compose change that removes a needed env, port or volume.
- Committed credentials, private keys, `.env` files.

---

# One-time setup

1. **Secrets — reuse Maestro's.** The skill uses the `GITHUB_TOKEN` (and `SLACK_BOT_TOKEN`
   for escalations) already saved in Maestro → Settings → Secrets; nothing new to add.
   The reviewer identity is **whoever owns that token** — `should-run.sh` resolves it via
   `GET /user`, so PRs authored by that account are skipped (GitHub forbids self-approval)
   and every other PR shows the approve under that account. For approvals to satisfy
   branch protection, that account needs **write** access (and a `CODEOWNERS` entry if
   code-owner review is required). If the reviews should appear as a bot instead of a
   person, swap the saved token for a machine user's later — no skill change needed.
2. **Maestro trigger.** Create a webhook trigger for `pr-auto-review` (same kind as
   `context-layer`'s). Default `input_kwargs` for the shadow week:
   `{"prr_shadow": true, "prr_repos": ["carespace-api"]}`. Remove both keys to go live.
3. **GitHub org webhook** (`carespace-ai` → Settings → Webhooks): payload URL
   `https://<maestro>/api/v1/webhooks/<trigger-token>`, content type `application/json`,
   events **Pull requests** + **Issue comments** only. The token URL is the only auth on
   this endpoint (no HMAC) — treat it as a secret.
4. **Label** `maestro:override` in each repo (optional; `/maestro approve` works without it).

# Run locally against a real PR (no posting)

```bash
export CLAUDEHUB_INPUT_KWARGS="$(gh api repos/carespace-ai/<repo>/pulls/<n> | python3 -c 'import json,sys; pr=json.load(sys.stdin); print(json.dumps({"action":"opened","repository":pr["base"]["repo"],"pull_request":pr}))')"
bash scripts/should-run.sh
bash scripts/fetch-context.sh carespace-ai/<repo> <n> <base_sha>
PRR_DRY_RUN=1 bash scripts/post-review.sh carespace-ai/<repo> <n> <head_sha> APPROVE /tmp/review.md
```

# Tests

`for t in tests/test-*.sh; do bash "$t"; done` — no network, no token needed.
