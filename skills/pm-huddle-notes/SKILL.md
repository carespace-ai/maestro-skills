---
name: pm-huddle-notes
description: Scan #pm-standup and #carespace-team for huddle note canvases AND huddle thread transcripts (7-day lookback), extract plaintext content, archive to GitHub vault. Idempotent — skips already-archived files.
---

# PM Huddle Notes

**Fully autonomous. Read-only on Slack. File-based pipeline — all data in /tmp files.**

## GUARDRAILS
- Read-only on Slack — NEVER posts, edits, or deletes messages in any channel
- Only reads from channels in $HUDDLE_SOURCE_CHANNELS — never substitutes
- Idempotent — checks vault before writing, skips existing files
- Max $HUDDLE_MAX_PER_RUN files written per run
- Skip files with fewer than $HUDDLE_MIN_CONTENT_CHARS chars of content
- ALL API responses go to /tmp files. NEVER dump raw JSON into context.
- GitHub vault writes use sha-based update (safe re-run — never duplicates)
- FAIL LOUDLY: a Slack API error (missing_scope, not_in_channel, channel_not_found)
  must abort or be reported as a BLOCKER — never report "complete" with 0 files collected

---

## REQUIRED SLACK BOT SCOPES

Verified by the Step 0 preflight — the run aborts with instructions if any is missing.

| Scope | Needed for |
|-------|-----------|
| `channels:read` | resolve public channel IDs |
| `groups:read` | resolve private channel IDs (#pm-standup) |
| `channels:history` | huddle-thread scan + canvas fallback in public channels |
| `groups:history` | same, in private channels |
| `files:read` | enumerate + download huddle canvases |
| `users:read` | resolve user IDs to names in transcripts |

Setup notes:
- Scope changes require **reinstalling** the Slack app to the workspace.
- The bot must be **invited** to every source channel (`/invite @<bot>` in
  #pm-standup and #carespace-team) — private channels are invisible to
  non-member bots even with `groups:read`, and `conversations.history`
  returns `not_in_channel` for public channels the bot hasn't joined.

## TRANSCRIPT ACCESS (verified 2026-08-20)

Slack stores each huddle's spoken transcript as a `huddle_transcript` file,
referenced in the AI-notes canvas footer (`File ID: sf:F...`). `files.info`
returns its metadata to bot tokens, but downloading the blob **302-redirects
to the workspace login for bot tokens** — a Slack platform restriction, not a
scope issue. Step 4 therefore always records `transcript_file_id` +
`transcript_url` in the archived note's frontmatter, and attempts the full
download with `$SLACK_USER_TOKEN` (a user `xoxp-` token) when set, falling
back to the bot token. The archivable records today are: the AI-notes canvas
(timestamped, per-speaker — Steps 2/4) and the huddle thread (Steps 5/6).

---

## EXECUTION PROTOCOL

Execute steps **one at a time** in order.

For each step:
1. Read the step file listed below using the Read tool
2. Execute the bash block exactly as written
3. Check output before proceeding

Do not read ahead. Only load the next step file after the current step completes successfully.

---

## STEPS

| # | File | Description |
|---|------|-------------|
| 0 | [steps/step-0-load-context.md](steps/step-0-load-context.md) | Source shared context + token/scope preflight (aborts on missing scopes) |
| 1 | [steps/step-1-resolve-channel-ids.md](steps/step-1-resolve-channel-ids.md) | Resolve channel names to IDs via paginated conversations.list |
| 2 | [steps/step-2-collect-canvas-files.md](steps/step-2-collect-canvas-files.md) | Scan channels for canvas files + huddle_thread anchors within lookback window |
| 3 | [steps/step-3-load-vault-index.md](steps/step-3-load-vault-index.md) | List existing vault huddle folders (informational) |
| 4 | [steps/step-4-download-archive.md](steps/step-4-download-archive.md) | Render canvas → markdown, write `<huddle-folder>/notes.md` (+ `transcript.md` when fetchable) |
| 5 | [steps/step-5-archive-threads.md](steps/step-5-archive-threads.md) | Fetch thread replies, render markdown, write `<huddle-folder>/thread.md` |

## VAULT LAYOUT

One folder per huddle, named `YYYY-MM-DD-HHMM-<channel>` (UTC huddle start,
derived from the huddle's `thread_ts` so Steps 4 and 6 pair automatically):

```
huddles/
└── 2026-08-20-1529-pm-standup/
    ├── notes.md        # AI canvas notes rendered as markdown (Step 4)
    ├── thread.md       # huddle thread messages (Step 5)
    └── transcript.md   # full spoken transcript — only when a token can fetch it (Step 4)
```

---

## /tmp FILE MAP

| File | Written by | Read by |
|------|-----------|---------|
| /tmp/huddle-channels.tsv | Step 1 | Step 2 |
| /tmp/huddle-files.tsv | Step 2 | Step 4 |
| /tmp/huddle-threads.tsv | Step 2 | Steps 4 (folder pairing), 5 |
| /tmp/vault-existing.txt | Step 3 | report only |
| /tmp/huddle-upload.md | Steps 4, 5 | intermediate |
| /tmp/huddle-log.txt | Steps 4, 5 | printed to stdout |
| /tmp/huddle-blockers.txt | Step 2 | error summary (missing scopes / invites) |
| /tmp/huddle-users.tsv | Step 1 | Steps 4, 5 |
| /tmp/huddle-users.sed | Step 1 | Step 4 (name substitution) |
| /tmp/huddle-channels.sed | Step 1 | Step 4 (channel-ID → name in titles) |
