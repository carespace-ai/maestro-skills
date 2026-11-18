# Catalog mirror (bulk analysis + exercise round-trip)

A local, on-disk copy of the catalog for questions that need the WHOLE collection at once —
coverage gaps, duplicate detection, cross-type correlation, vocabulary reconciliation — where
paging through `list_*`/`get_*` MCP calls one record at a time is slow and, for relations,
incomplete (see Why REST below). The mirror is read with ordinary file tools (`grep`, `jq`,
a script) against JSON already on disk; nothing here is a substitute for the MCP authoring
flows in `SKILL.md` — it is a faster lens onto the same data for analysis.

> **Interpreter name:** the commands below say `python3`, which is right on macOS and Linux.
> On Windows resolve it first (`python3` → `python` → `py -3`) and substitute throughout. See
> the operator note in `SKILL.md`.

## Taking a snapshot

    python3 scripts/snapshot.py --env <env> [--types a,b] [--root PATH]

- **Config** — reads `STRAPI_HOST` and `STRAPI_READ_TOKEN`, either from the environment or
  from `${CLAUDE_PLUGIN_DATA}/.env` (written automatically by the plugin's `SessionStart` hook
  from the physio's stored Strapi **API Token** — Settings → API Tokens, distinct from the
  Admin Token the MCP connection uses — see `SKILL.md`'s Setup wizard). A read-only API Token
  is enough; snapshot never writes. Missing either raises immediately — same `ConfigError`
  shape as any other REST config problem in this skill.
- **`--env`** is a free-form label (`staging`, `prod`, …) used only to namespace the output
  tree — it does not resolve an MCP registration the way `run_job.py --env` does.
- **`--types`** — comma list restricting the run to a subset of the five types below; default
  is all five.
- **Output root** — `--root`, else `$CARESPACE_MIRROR_ROOT`, else `~/carespace-catalog-mirror`.
  Layout: `<root>/<env>/<type>/<carespaceId>.json` plus one `<root>/<env>/manifest.json`
  (env, fetch timestamp, per-type record counts) written after the run.
- **Five types**, the same singular type ids used everywhere else in this skill: `exercise`,
  `program-template`, `calendar-program-template`, `omni-rom-program`, `survey-template`.
- **Relations are rendered as NAMES**, not ids or bare counts — a record on disk shows
  `"joints": ["Hip", "Knee"]`, not `{"count": 2}`. That's the entire point of reading via REST
  instead of MCP (next section). Each mapped record also carries a `_snapshot` block
  (`documentId`, `source_updatedAt`, and — for exercises — `linked_subrecords`, the existing
  Class-B sub-record ids captured for replace-on-write) that the round-trip below depends on.

## Why REST, not MCP

Download is REST-only (`scripts/rest_client.py`, stdlib `urllib`, `populate=*`, paginated at
`pageSize: 100`) because **MCP reads return every relation as a bare `{"count": N}`** — no
names, no ids (see `recipes.md` → Verified surface behaviors, "Relations can't be filtered or
enumerated via MCP"). A catalog-wide question ("which exercises are missing a `reasons` link",
"which `body_regions` name is never used") is unanswerable from MCP reads alone; REST's
`populate=*` is the only surface that returns the actual linked names. This does not change how
writes happen — MCP + the job runners remain the only write path (below).

## The exercise round-trip

Editing FROM the mirror is supported for `exercise` only (see Invariants). The flow:

1. **Edit a mirror record.** Open `<root>/<env>/exercise/<carespaceId>.json` and change its
   `scalars`, `relations`, `classA`, or `classb` content directly — same field names and
   Class-A/Class-B shapes as `recipes.md` → Exercise and `templates/scan-fill.json`.

   **v1 write-back scope, by field group:** `scalars` overwrite normally. `classb` round-trips
   as a full replace (see step 3). `relations` and `classA` are **additive only** —
   `scan_fill.py` only ever `connect`s the names present on the mirror record; it does not
   diff against what's already linked. Adding a joint/tag/reason to the mirror record and
   writing it back connects it as expected, but *removing* one from the mirror record is
   **not** applied — the old link stays connected on write-back. To remove a `relations` or
   `classA` link, do it in the Strapi admin UI directly; replace-on-write for these two groups
   is a v2 update-runner follow-up.
2. **Turn it into a job:**

       python3 scripts/mirror_to_job.py <record.json> <job-dir> [--env <env>]

   This filters the record to the writable subset — `is_bilateral` is dropped; it's
   middleware-derived from `laterality` and is never written directly — and, when `--env` is
   passed, drift-checks the record against the live one via REST `get_one`: if the live
   `updatedAt` no longer matches the snapshot's `_snapshot.source_updatedAt`, it prints a DRIFT
   message and **exits 2** without writing anything (re-snapshot and re-edit before retrying).
   On success it emits a scan-fill `plan.json` (`kind: scan-fill`, `batch: [<carespaceId>]`)
   and `records/<carespaceId>.json` in `<job-dir>` — the same shapes `run_job.py` already
   consumes for any other scan-fill job.
3. **Run it** the normal way:

       python3 scripts/run_job.py <job-dir> --env <mcp-registration>

   `scan_fill.py`'s write path is unchanged except for one behavior needed by round-trips: on
   a manyToMany Class-B field with prior links (`_snapshot.linked_subrecords`), it now
   **REPLACES** rather than adds — it creates the new sub-records, then connects them and
   **disconnects** the old ids in the same `update_exercise` call, instead of leaving the
   superseded content additively linked. A field with no prior links behaves exactly as
   scan-fill always has: connect only.
4. **Draft, then sign-off as usual.** The write lands as a draft, `review_status: unreviewed` —
   nothing here approves or publishes. The physio reviews and signs off in the Review & publish
   flow, same as any other scan-fill batch.

## Invariants (unchanged by the mirror)

- **Drafts only.** Every mirror-driven write goes through `run_job.py`, which never sets
  `review_status: approved` or calls a `publish_*` tool. Sign-off stays entirely in the Review
  & publish flow.
- **v1 scope: exercise write-back only.** `mirror_to_job.py` and the round-trip above apply to
  `exercise` records. `program-template`, `calendar-program-template`, `omni-rom-program`, and
  `survey-template` mirror records are **snapshot-for-analysis only** — read them freely for
  coverage/correlation questions, but author or edit them the normal way, through the
  compose-* job flows in `SKILL.md`, not from the mirror. Wiring in-place edits for those four
  is a v2 follow-up.
- **No delete.** The round-trip's Class-B replace disconnects superseded sub-records from the
  exercise; it never deletes them. Same orphan-sweep-elsewhere rule as everywhere else in this
  skill.
- **Orphans accumulate.** Each exercise round-trip creates fresh Class-B sub-records and
  unlinks (never deletes) the superseded ones, so repeated round-trips on the same exercise
  accumulate orphaned Class-B drafts over time — these are swept separately (see the
  orphan-sweep note elsewhere in this skill), never by this flow.

## Drift guard

The mirror is a point-in-time copy — if a record changed live after it was snapshotted (another
session, the admin UI), writing a stale edit back would silently clobber that change. Passing
`--env` to `mirror_to_job.py` catches this: it re-reads the live record via REST and compares
`updatedAt` against the snapshot's `_snapshot.source_updatedAt` before building the job. A
mismatch means someone else changed the record after the snapshot was taken — re-run
`snapshot.py` for a fresh copy, redo the edit, and retry rather than forcing the write. Omitting
`--env` skips the check entirely; only do that when you're certain nothing else could have
touched the record since the snapshot (e.g. immediately after taking it).
