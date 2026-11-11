Python service (FastAPI + Agent Framework) behind the clinician / patient
assistant in carespace-mobile. It reads and — after an explicit confirmation —
writes carespace-admin data with the caller's own credentials, reads Strapi, and
streams answers to the app over SSE. Deployed on its own, independently of the app.

## What breaks here

The numbered "Hard rules" in AGENTS.md are this repo's invariants. A PR that
makes one of these false is a blocker — cite the rule number:

- **PHI in a log line or trace** (rule 1) — conversation text, patient ids or
  names reaching a logger, an exception message or telemetry; content capture turned on.
- **More than the caller's credentials** (rule 2) or **a backend call that skips the
  scope guard** (rule 3) — a tool that reaches a patient id without `CaseloadGuard`.
- **A write that does not go through a confirmation** (rules 4, 12, 14) — a tool
  calling a mutating operation directly, or an AI draft that persists before Confirm.
- **The model choosing an endpoint, URL, route or credential** (rule 5).
- **A raw error reaching the client** instead of a fixed `sse.ERROR_MESSAGES` string (rule 6).
- **Anything but GET against Strapi** (rule 11); plain `http://` to a dependency (rule 7).
- **An SSE or card change the shipped app cannot read** — removing or renaming an
  event type, a card `kind` or a card field, or changing a field's type. The app in
  the stores keeps talking to this service after the deploy. (A *new* card `kind`
  or optional field is additive and fine.)
- **A new required setting with no default that is missing from `infra/` parameters**
  — the container fails to start on deploy.

## Not a blocker here

- Prompt wording, `PROMPT_VERSION` bumps, tool descriptions and analyzer thresholds
  — product decisions, unless they contradict a hard rule.
- Tests, ruff / typing findings and the eval gate — CI.
- Docs under `docs/` and status notes in design documents.
