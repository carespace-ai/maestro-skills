# Repo review profiles

One directory per reviewed repo. `fetch-context.sh` stages the profile of the
PR's repo into `$PRR_DIR/profile.md`; a repo without a directory here is still
reviewed, with generic stack checklists and generic risk paths.

```
repos/
  _template/        copy this to add a repo
  <repo-name>/
    profile.json    machine-read: stacks, risk paths, CI checks to ignore
    review.md       read by the reviewer: how this repo breaks, what not to flag
```

The profile lives **here**, not in the reviewed repo, so a PR can never edit the
rules it is reviewed by. Architecture and conventions stay in the repo's own
`AGENTS.md` (Context Layer) — do not copy them into `review.md`.

## profile.json

| Key | Meaning |
|-----|---------|
| `repo` | repo name, identical to the directory name |
| `default_branch` | branch PRs target |
| `stacks` | `{stack: [globs]}` — a stack's checklist (`../stacks/<stack>.md`) is loaded when a changed file matches one of its globs |
| `risk_paths` | `[{glob, why}]` — a changed file matching one is listed for the reviewer to read in full, however large the PR |
| `human_paths` | `[glob]` — a PR that changes a matching file is never approved by the bot: it posts its findings as a comment and asks for a human approve. Keep it short (every entry reintroduces waiting); `[]` opts out |
| `ci_ignore` | regex of check names that must never hold an approve (flaky or advisory jobs); empty = every check counts |

Globs: `**` crosses directories, `*` and `?` stay inside one path segment.

## Relations (`../relations.json`)

One edge per contract between two repos:

| Key | Meaning |
|-----|---------|
| `id` | short stable name of the contract |
| `provider` / `consumer` | repo that exposes the surface / repo that depends on it |
| `coupling` | `immediate` — the consumer meets a change as soon as the provider ships (separate deploys, runtime contract, path dependency) → a break is a blocker. `deferred` — the consumer is pinned to a released version → a break is a heads-up |
| `surface` | what the contract is, in one sentence |
| `provider_paths` | provider files that define the surface — a PR touching them triggers the provider-side check |
| `consumer_paths` | consumer files that use it — a PR touching them triggers the consumer-side check; also what gets staged for a provider-side check |
| `provider_stage` | optional: the compact machine-readable contract to stage for consumer-side checks (e.g. `openapi.json`) instead of every provider source |

An edge works as soon as **one** end is reviewed; the other end only needs to be
readable by the reviewer identity (GitHub App installed) to be staged — if it is
not, the review says the contract was not verified and carries on.

## Add a repo

1. `bash ../scripts/onboard-repo.sh carespace-ai/<repo-name>` — generates
   `<repo-name>/profile.json` from the repo's file tree, drops the `review.md`
   template and an `ONBOARDING.md` to-do list quoting the repo's own rules, and
   prints `READY_*` lines for everything enrolment needs (Context Layer, webhook,
   ruleset, override label). Work through `ONBOARDING.md`, then delete it.
   (By hand: `cp -r _template <repo-name>` and fill both files.)
2. Add its contracts to `../relations.json` — one edge per repo it calls and per
   repo that calls it. Take them from the "App Integration" table of its
   `AGENTS.md`, then **check each path exists on both sides**.
3. `python3 ../scripts/validate-registry.py` — must print `REGISTRY_ERRORS=0`.
4. Dry-run against a few merged PRs of that repo (REFERENCE.md › Run locally).
5. Enrol the repo for delivery: GitHub App installed, webhook orchestrated in
   Maestro, repo added to the trigger's `prr_repos`.

A profile and enrolment are independent: the profile only changes *how* a repo is
reviewed, `prr_repos` decides *whether* it is.
