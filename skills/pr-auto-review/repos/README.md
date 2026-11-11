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
| `ci_ignore` | regex of check names that must never hold an approve (flaky or advisory jobs); empty = every check counts |

Globs: `**` crosses directories, `*` and `?` stay inside one path segment.

## Add a repo

1. `cp -r _template <repo-name>` and fill both files (`review.md` from the repo's
   `AGENTS.md` hard rules / integration contracts and its recent incident history).
2. `python3 ../scripts/validate-registry.py` — must print `REGISTRY_ERRORS=0`.
3. Dry-run against a few merged PRs of that repo (REFERENCE.md › Run locally).
4. Enrol the repo for delivery: GitHub App installed, webhook orchestrated in
   Maestro, repo added to the trigger's `prr_repos`.

A profile and enrolment are independent: the profile only changes *how* a repo is
reviewed, `prr_repos` decides *whether* it is.
