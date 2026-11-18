# Dependency recipes & consumer contracts

Composition order, consumer contracts, and authoring discipline for writing carespace-strapi
content through the MCP tools. This file is hand-authored — the generated `model-map.md` and
`authoring-*.md` in this directory are the schema source of truth; if anything here ever
disagrees with them, the generated file wins and this one is wrong.

## Job workflows

Multi-write flows run as declarative **jobs**: a `plan.json` (+ optional `records/`) executed by
`scripts/run_job.py` against the five runner kinds. The per-kind plan shapes are in the skill's
`templates/` directory (`compose-program.json`, `compose-survey.json`, `compose-calendar.json`,
`publish-chain.json`, `scan-fill.json`, plus `brief.md`); the SKILL.md "Job workflows" section is
the operating procedure.

These recipes remain the CONTRACT — what must be true (composition order, connect semantics, the
dosing quintet, the publish gate). The jobs are the EXECUTION — how it runs reliably and resumably.
When a runner or template DISAGREES with these recipes, recipes + the generated `authoring-*.md`
/ `model-map.md` win and the runner has a bug to fix.

MCP tool names below follow the `<verb>_<type-id>` convention where `<type-id>` is ALWAYS the
SINGULAR type id (verified live): `list_exercise`, `create_exercise-tag`, `publish_survey-template`,
`discard_<type-id>_draft`. The plural form in `model-map.md` is the REST id only, never a tool name (the
singular type id — the `##` heading in `model-map.md`).

**Verified surface behaviors (live smoke, Strapi 5.47.1):**

- **Envelopes** — `list_*` returns `{results, pagination}` (the content-manager shape), NOT
  REST's `{data, meta}`; `create_*` / `get_*` / `update_*` return `{data: {...}}`.
- **Filters** — the `filters` argument accepts a bare value for equality, or an operator
  object whose operator values are STRINGS: `{"instructions": {"$notNull": "true"}}` works;
  a boolean `true` is rejected by the schema layer.
- **Relation writes** — a to-many relation value must be a connect object:
  `{"connect": [{"documentId": "..."}, ...]}` — a bare documentId array is rejected. An
  x-to-one relation accepts a bare documentId string (verified to link on read-back).
- **`pageSize` max is 100** — larger values are rejected. Collections over 100 rows
  (e.g. `exercise-target-muscle-group`, 119) need `page: 2` and up.
- **Numeric filters need care** — a string value on an integer field matches NOTHING,
  silently: `{"carespaceId": {"$eq": "322"}}` returns an empty result instead of an error.
  Filter by a string field (e.g. `name` with `$containsi`) when hunting a specific record.
- **`update_*` validates the FULL document, not a patch** — every required field must be
  present in `data` even if unchanged (`carespaceId`, `review_status`, `machine_clearance`,
  …). For a legacy row with nulls, supply the NEUTRAL values (`unreviewed`, `unevaluated`)
  — never a value that asserts review or clearance that hasn't happened.
- **x-to-one links: bare documentId string, and re-read WITH populate to verify.** At create,
  a bare-string value linked a oneToOne (`strapiExerciseId`) but was silently DROPPED on a
  manyToOne (`exercise-modification-option.level`) — accepted by validation, never linked.
  The same bare-string value on `update_*` DID link it (and a `{connect:[...]}` object on
  that x-to-one update was rejected — connect objects are for to-many only; the accepted
  x-to-one shapes are a bare string, `{"documentId": "..."}`, or `null` to clear).
- **Verifying a link: pass `populate`, and NEVER read `None` as "dropped".** `get_*` default-
  populates *some* to-many relations/components (a program's `exercises`, a calendar's `days`,
  a survey's questions all read back as `{"count": N}` with no populate arg — the compose
  runners rely on this), but does NOT default-populate a oneToOne like `exercise.modification_options`
  or the nested `…-modification-option.level`. Read those with `populate: "*"` (or a field list):
  a linked x-to-one then reads `{"count": 1}`. A bare `None` on an UNPOPULATED read means
  nothing — it is the "filled-field-shows-null" trap. Only `None` on a POPULATED read means the
  link is actually absent. (scan-fill's live smoke first mis-read a good link this way.)
- **Relations can't be filtered or enumerated via MCP.** `filters` accepts scalar fields
  only (a relation key is `unrecognized_keys`), and reads return every relation as a bare
  `{"count": N}` — no names, no ids. You cannot list which records an exercise already
  links through MCP: track what you wrote in-session, and verify pre-existing links in the
  Strapi admin UI (this matters wherever `connect`'s additive behavior meets a record that
  already has links).
- **`connect` is ADDITIVE** — it appends to a relation without removing existing links. On
  a record that already has links, review what is already there first; to REPLACE, use
  `set` semantics or disconnect explicitly, and always re-read the record after writing to
  see the true combined state.
- **Tool availability mirrors the admin token's permissions, per session.** A verb family
  the token can't perform is missing from `tools/list` or answers `Tool <name> disabled` at
  call time — a listed tool is not proof it is callable. On 5.47.1, `publish_*`/`unpublish_*`
  were observed disabled at call time even for full-access tokens (see Publish availability
  below).
- **Bulk reads are REST, not MCP.** `scripts/snapshot.py` mirrors the catalog to local JSON via
  REST `populate=*` (`scripts/rest_client.py`), never MCP — MCP relations read as bare
  `{"count": N}` with no names or ids, so a catalog-wide question (coverage, duplicates,
  cross-type correlation) is unanswerable from MCP reads alone. Write-back stays MCP + the job
  runners exactly as elsewhere in this file — see `references/catalog-mirror.md` for the full
  workflow and the exercise round-trip via `mirror_to_job.py`.
- **Memory (ops caveat)** — the 5.47 MCP beta retains heap per call (~20–30 MB observed;
  `tools/list` is by far the heaviest — it serializes every content type's full schema).
  Keep sessions few and calls frugal, never poll `tools/list`, and expect the server to need
  restarts under sustained agent load. Do NOT enable MCP on production until the leak is
  fixed upstream — a busy agent can crash the CMS (availability risk). Keep it disabled via
  `MCP_ENABLED=false` (`mcp.enabled` in carespace-strapi's `config/server.js`).

## Universal recipes

- **Next id** — every MCP create requires an explicit `carespaceId`. Allocate one by calling
  `list_<type-id>` sorted `carespaceId:desc`, page size 1, and using max + 1 (or `1` when the
  collection is empty). The server's auto-id counter bumps past explicit ids on create, so
  this never collides with an id assigned through the admin UI.
- **Draft-first** — MCP creates land as drafts (`publishedAt: null`; verified live). Never
  call a `publish_*` tool outside the Review & publish flow.
- **Publish order** — children before parents: exercise sub-content before the exercise;
  join records (`program-exercise-template`, `omni-rom-program-exercise`,
  `survey-template-question`) before the template that references them; programs, OmniROM
  programs, and surveys before the calendar template that schedules them. A published parent
  must never point at an unpublished child.
- **Publish availability** — before the Review & publish flow relies on MCP publishing,
  probe ONE `publish_<type-id>` call. Availability tracks the token's permission grants and
  has varied between otherwise-similar tokens on 5.47.1: some full-access mints answered
  `Tool <name> disabled` on every publish call, while a later full-access mint published
  successfully. Never assume from the tools listing — the probe is the truth. If publish
  is unavailable: still stamp the review fields via `update_*` (the signature), then hand
  the actual Publish clicks to the physio in the Strapi admin (children before parents, same
  order as below), linking each draft by documentId. Never fake a publish by other means.
- **Retire/replace** — to remove a relation, unlink it (write the new relation array, or
  null the oneToOne). Never delete a record that other content may share. `delete_*` tools
  DO exist and work when the token grants delete (verified live) — so this is discipline,
  not a structural guarantee: mint authoring tokens WITHOUT the delete permission and the
  surface enforces it for you. 5 of the 6
  exercise sub-content relations are manyToMany and are genuinely shared in live data (e.g.
  59 of 100 `exercise-cool-down-recommendation` rows link to more than one exercise) —
  deleting one silently breaks every other exercise that pointed at it.
- **Validation** — MCP's schema layer rejects bad fields, enums, and missing required
  values server-side. Surface its error verbatim to the caller; never invent a value just to
  get past validation.

## Exercise

Nine of the exercise's authorable fields are relation-backed sub-content rather than plain
scalars, and split into two classes with different authoring rules.

**Class A — controlled vocabulary.** Terms must exist verbatim (case-insensitive) in the
checked-in standard, `controlled-vocabularies.json`. Look up the record by name via the
type's `list_*` tool; create it (as a draft, canonical spelling) only if it is genuinely
absent — never force-match a near-term.

| Field | Backing type | Lookup/create tool |
|---|---|---|
| `tags` | `exercise-tag` (manyToMany) | `list_exercise-tag` / `create_exercise-tag` |
| `functional_goals` | `functional-goal` (manyToMany) | `list_functional-goal` / `create_functional-goal` |
| `exercise_target_muscle_groups` | `exercise-target-muscle-group` (manyToMany) | `list_exercise-target-muscle-group` / `create_exercise-target-muscle-group` |
| `modification_options.level` | `exercise-modification-option-level` (oneToOne, nested under `exercise-modification-option`) | `list_exercise-modification-option-level` / `create_exercise-modification-option-level` |

**Class B — authored per exercise.** Free text written for this exercise, not drawn from
any fixed list; each item is its own draft sub-record, created fresh and linked by
documentId.

| Field | Backing type | Item shape |
|---|---|---|
| `common_mistakes` | `exercise-common-mistake` (manyToMany) | `{description}` |
| `feedback_points` | `exercise-feedback-point` (manyToMany) | `{description}` |
| `warm_up_suggestions` | `exercise-warm-up-suggestion` (manyToMany) | `{description, duration}` |
| `cool_down_recommendations` | `exercise-cool-down-recommendation` (manyToMany) | `{description, duration}` |
| `progression_steps` | `exercise-progression-step` (manyToMany) | `{step, description}` — `step` sequential `1..N`, no gaps or duplicates |
| `modification_options` | `exercise-modification-option` (oneToOne) | `{description, level}` — single item, not an array; `level` is itself the Class-A controlled term above |

Linking is by documentId: manyToMany fields take an array, the oneToOne field takes a
single id (or `null` to clear). Editing an exercise's sub-content replaces the link set —
it does not delete the superseded record. Leave it unlinked; orphaned sub-content is swept
separately, not by the authoring flow.

Never set `review_status`, any `machine_*` field, or `publishedAt` when authoring or
editing an exercise. `review_status: approved` plus the `reviewed_by`/`reviewed_at` stamp
are written only by the Review & publish flow, never by a create/edit call.

## Program

Order of operations, id-allocation and all:

1. Confirm each exercise exists (by `carespaceId`) and is complete enough to prescribe.
2. Allocate join ids (Universal recipes → Next id).
3. `create_program-exercise-template` per exercise — `strapiExerciseId` (the exercise's
   documentId, oneToOne) plus the dosing quintet `weeklyReps`, `dailyReps`, `sets`, `reps`,
   `order`: **all five must be non-null before this row may ever be published** (backend
   consumer contract). `name` convention: `"<program> — <exercise> (sets×reps)"`.
4. Allocate a `carespaceId` for the program itself.
5. `create_program-template` — `name`, `duration` (required), `durationType` (required;
   `days`\|`weeks`\|`months`\|`years`), the join documentIds in `exercises`, and the taxonomy
   relations `body_regions` / `joints` / `functional_goals` / `reasons` (names resolved via
   each type's `list_*`).

## Calendar template

1. Confirm every referenced `program-template`, `omni-rom-program`, or `survey-template`
   already exists — create it first via its own recipe above.
2. Compose `days` as INLINE component objects: components are embedded directly in the
   `calendar-program-template` payload, never created as separate records. Each day is
   `{dayNumber ≥ 1, order ≥ 0, activityType, <exactly the relations that activityType gates>}`.
   Never populate a relation that doesn't match the day's `activityType`.

   | `activityType` | Required relation | Optional relation |
   |---|---|---|
   | `exercise` | `exerciseProgram` (oneToOne → `program-template`) | `exerciseItems` (subset, manyToMany → `program-exercise-template`) |
   | `omniRom` | `omniRomProgram` (oneToOne → `omni-rom-program`) | `omniRomExercises` (subset, manyToMany → `omni-rom-program-exercise`) |
   | `survey` | `surveyTemplate` (oneToOne → `survey-template`) | — |
   | `evaluation` / `posture` / `bodyComposition` | none | none |

3. `create_calendar-program-template` — `name` (required), `weeks` (1–52; the backend
   computes each day's date as `startDate + (dayNumber-1)`), and `experienceLevel` (required).
   > Calendar `reasons` and `experienceLevelRef` are not yet wired through the job runner
   > (a known follow-up); `compose_calendar` writes only `name`/`weeks`/`experienceLevel`/`days`.

## OmniROM

**Programs** are composed from existing `omni-rom-exercise` records — never created fresh
as part of program authoring:

1. `create_omni-rom-program-exercise` per exercise — `OmniRomExerciseId` (documentId,
   oneToOne) and `order` (required).
2. `create_omni-rom-program` — `title` (required).

**Creating an `omni-rom-exercise` itself** (its own, separate track):

- `name` (required), `order` (required, **unique across the type** — check the current max
  first).
- `mobilityMapper` (required; 13 values: `rightShoulder` \| `leftShoulder` \| `rightElbow` \|
  `leftElbow` \| `rightHip` \| `leftHip` \| `rightKnee` \| `leftKnee` \| `squat` \| `neck` \|
  `lumbar` \| `leftWrist` \| `rightWrist`) and `cameraPosition` (required; `facing_front` \|
  `facing_back` \| `left_side` \| `right_side` \| `facing_front_seated` \|
  `left_side_seated` \| `right_side_seated`) — from their enums only, never invented.
- `function` (required text) is backend-eval'd code, not authored prose — copy it verbatim
  from an existing exercise of the same joint/side, or obtain it from an engineer. Never
  compose it.
- `video` and `image` are both required media. Reference existing upload ids only — if none
  exist for this exercise, stop at "draft blocked on media" and hand off; do not fabricate
  or substitute an unrelated asset.
- CV/scoring components (`pointsToCalculateAngle`, `pointsToValidatePosition`) are out of
  scope for this flow.

## Survey

1. `create_survey-template-question` per question — `title` and `description` (both
   required), `questionType` (required; `rate` \| `singleSelect` \| `multiSelect` \|
   `openText`), `scored`, `order`.
2. `create_survey-template` — `title` and `description` (both required), `clinicallyValidated`
   (leave `false` unless the physio explicitly attests otherwise), `edit`, linking the
   questions via `surveyTemplateQuestion`.

## Attribution & environments

MCP writes are `createdBy` the admin-token owner — there is no per-write actor field.
Exercise sign-off identity comes from the `reviewed_by` stamp set at approval, not from
authorship. Per-physio attribution therefore requires a per-physio admin token
(`claude mcp add` once per person, per environment). Name registrations `strapi-<env>`.

Before any write batch against an environment the user has called production, require a
typed PROD confirmation in-chat — do not infer consent from context.
