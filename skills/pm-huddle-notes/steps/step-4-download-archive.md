# Step 4: Download + Archive New Huddles → vault folders + /tmp/huddle-log.txt

Each huddle gets ONE FOLDER in the vault, named after the huddle's UTC start time:

```
huddles/2026-08-20-1529-pm-standup/
├── notes.md        # AI canvas notes, rendered as markdown (this step)
├── thread.md       # huddle thread messages (Step 5)
└── transcript.md   # full spoken transcript, only when a token can fetch it (this step)
```

The folder anchor is the huddle's `thread_ts` (extracted from the canvas's
"View huddle in channel" link) so notes and thread land in the same folder;
falls back to the canvas creation time if no link is present.

Canvas HTML is converted to GitHub-flavored markdown via `scripts/canvas2md.py`
(headings, nested lists, bold, links preserved; emoji shortcodes left for GitHub
to render). User mentions are bolded and resolved to display names.

```bash
source ~/.claude/skills/_pm-shared/context.sh
CANVAS2MD=~/.claude/skills/pm-huddle-notes/scripts/canvas2md.py
> /tmp/huddle-log.txt
WRITTEN=0; SKIPPED=0; ERRORS=0; ITER=0; MAX=$HUDDLE_MAX_PER_RUN

# Helper: create-or-update one vault file from /tmp/huddle-upload.md
# Usage: vault_put <path-in-repo> <commit-msg>   → echoes OK / ERROR
vault_put() {
  local dest="$1" msg="$2"
  local b64 sha payload result
  b64=$(base64 -w0 /tmp/huddle-upload.md)
  sha=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$dest" --jq '.sha' 2>/dev/null || echo "")
  if [ -n "$sha" ]; then
    payload=$(jq -n --arg msg "$msg" --arg content "$b64" --arg sha "$sha" \
      '{message: $msg, content: $content, sha: $sha}')
  else
    payload=$(jq -n --arg msg "$msg" --arg content "$b64" \
      '{message: $msg, content: $content}')
  fi
  result=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$dest" \
    -X PUT --input - <<< "$payload" --jq '.content.name // "ERROR"' 2>&1)
  if [ "$result" = "ERROR" ] || echo "$result" | grep -q '"message"'; then
    echo "ERROR: $dest → $result" >> /tmp/huddle-log.txt; echo ERROR
  else
    echo OK
  fi
}

while IFS=$'\t' read -r channel file_id created_ts name url_private; do
  [ $WRITTEN -ge $MAX ] && echo "HIT MAX $MAX writes — stopping" >> /tmp/huddle-log.txt && break
  ITER=$((ITER+1))

  # Skip if no URL
  if [ -z "$url_private" ]; then
    SKIPPED=$((SKIPPED+1))
    echo "SKIP (no url): $name" >> /tmp/huddle-log.txt
    continue
  fi

  # Download raw canvas content
  RAW=$(curl -sL "$url_private" -H "Authorization: Bearer $SLACK_BOT_TOKEN")

  # Folder anchor = huddle start ts. Resolution chain (each source is missing on
  # some canvases, verified live): (1) files.info shares.thread_ts, (2) the
  # "View huddle in channel" link inside the canvas HTML, (3) the latest huddle
  # thread in the same channel that started ≤3h before the canvas was created,
  # (4) the canvas creation time.
  FINFO=$(curl -s "https://slack.com/api/files.info?file=${file_id}" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  HUDDLE_TS=$(echo "$FINFO" | jq -r '[.file.shares // {} | .. | objects | .thread_ts? // empty] | first // ""')
  [ -z "$HUDDLE_TS" ] && \
    HUDDLE_TS=$(printf '%s' "$RAW" | grep -o 'thread_ts=[0-9]*\.[0-9]*' | head -1 | cut -d= -f2)
  ANCHOR=${HUDDLE_TS%%.*}
  if [ -z "$ANCHOR" ] && [ -s /tmp/huddle-threads.tsv ]; then
    ANCHOR=$(awk -F'\t' -v ch="$channel" -v c="$created_ts" \
      '$1==ch { t=int($3); if (t<=c && c-t<10800 && t>best) best=t } END{if(best) print best}' \
      /tmp/huddle-threads.tsv)
    [ -n "$ANCHOR" ] && HUDDLE_TS=$(awk -F'\t' -v ch="$channel" -v a="$ANCHOR" \
      '$1==ch && int($3)==a {print $3; exit}' /tmp/huddle-threads.tsv)
  fi
  [ -z "$ANCHOR" ] && ANCHOR=$created_ts
  # -u: folder names must be timezone-independent (UTC) so every runner agrees
  FDATE=$(date -u -d "@$ANCHOR" +%Y-%m-%d 2>/dev/null || echo "unknown")
  FTIME=$(date -u -d "@$ANCHOR" +%H%M       2>/dev/null || echo "0000")
  DIR="${FDATE}-${FTIME}-${channel}"
  DEST="$HUDDLE_VAULT_PATH/$DIR/notes.md"

  # Idempotency: skip if notes.md already exists in this huddle's folder
  if gh api "repos/$HUDDLE_VAULT_REPO/contents/$DEST" --jq '.sha' >/dev/null 2>&1; then
    SKIPPED=$((SKIPPED+1))
    echo "SKIP (exists): $DIR/notes.md" >> /tmp/huddle-log.txt
    continue
  fi

  # Render to markdown. Canvas exports start with <div class="quip-canvas-content">
  # (no <html>/<!DOCTYPE>) — detect ANY opening tag.
  if echo "$RAW" | grep -q '<[a-zA-Z][^>]*>'; then
    CONTENT=$(printf '%s' "$RAW" | python3 "$CANVAS2MD")
  elif echo "$RAW" | jq . >/dev/null 2>&1; then
    # JSON canvas format — extract text blocks
    CONTENT=$(echo "$RAW" | jq -r '
      .. | objects | select(.type == "text" or .type == "rich_text")
         | (.text // .elements // []) | if type == "array" then .[].text? // "" else . end
    ' 2>/dev/null | grep -v '^$')
  else
    CONTENT="$RAW"
  fi

  # Bold user mentions, then resolve user IDs → names and channel IDs → names
  CONTENT=$(printf '%s' "$CONTENT" | sed 's/@\(U[A-Z0-9]\{8,\}\)/**@\1**/g')
  [ -s /tmp/huddle-users.sed ]    && CONTENT=$(printf '%s' "$CONTENT" | sed -f /tmp/huddle-users.sed)
  [ -s /tmp/huddle-channels.sed ] && CONTENT=$(printf '%s' "$CONTENT" | sed -f /tmp/huddle-channels.sed)

  # Discover the huddle_transcript file referenced in the canvas footer.
  # Bot tokens CANNOT download huddle_transcript blobs (Slack 302s to login) —
  # metadata is always recorded in frontmatter; full content is archived only
  # if a token with access is available (set SLACK_USER_TOKEN to try a user token).
  TR_ID=$(printf '%s' "$CONTENT" | grep -o 'File ID: sf:F[A-Z0-9]*' | head -1 | sed 's/.*sf://')
  TR_PERMALINK=""; TR_DL=""
  if [ -n "$TR_ID" ]; then
    TINFO=$(curl -s "https://slack.com/api/files.info?file=${TR_ID}" \
      -H "Authorization: Bearer $SLACK_BOT_TOKEN")
    if [ "$(echo "$TINFO" | jq -r '.ok')" = "true" ]; then
      TR_PERMALINK=$(echo "$TINFO" | jq -r '.file.permalink // ""')
      TR_DL=$(echo "$TINFO" | jq -r '.file.url_private_download // .file.url_private // ""')
    fi
  fi

  CLEN=${#CONTENT}
  if [ "$CLEN" -lt "$HUDDLE_MIN_CONTENT_CHARS" ]; then
    SKIPPED=$((SKIPPED+1))
    echo "SKIP (empty ${CLEN}c): $name" >> /tmp/huddle-log.txt
    continue
  fi

  {
    printf -- '---\n'
    printf 'date: %s\n' "$FDATE"
    printf 'source: slack-huddle\n'
    printf 'channel: "%s"\n' "$channel"
    printf 'slack_file_id: "%s"\n' "$file_id"
    [ -n "$HUDDLE_TS" ] && printf 'huddle_thread_ts: "%s"\n' "$HUDDLE_TS"
    [ -n "$TR_ID" ] && printf 'transcript_file_id: "%s"\n' "$TR_ID"
    [ -n "$TR_PERMALINK" ] && printf 'transcript_url: "%s"\n' "$TR_PERMALINK"
    printf 'archived_by: pm-huddle-notes\n'
    printf -- '---\n\n'
    printf '%s\n' "$CONTENT"
  } > /tmp/huddle-upload.md

  if [ "$(vault_put "$DEST" "huddle: $FDATE #$channel — notes archived by pm-huddle-notes")" = "OK" ]; then
    WRITTEN=$((WRITTEN+1))
    echo "WRITE: $DIR/notes.md (${CLEN}c)" >> /tmp/huddle-log.txt
  else
    ERRORS=$((ERRORS+1))
  fi

  # Best-effort full transcript archive (works only with a token Slack lets
  # download huddle_transcript files — currently NOT bot tokens)
  if [ -n "$TR_ID" ] && [ -n "$TR_DL" ]; then
    TDEST="$HUDDLE_VAULT_PATH/$DIR/transcript.md"
    if gh api "repos/$HUDDLE_VAULT_REPO/contents/$TDEST" --jq '.sha' >/dev/null 2>&1; then
      echo "SKIP (exists): $DIR/transcript.md" >> /tmp/huddle-log.txt
    else
      TRAW=$(curl -sL "$TR_DL" -H "Authorization: Bearer ${SLACK_USER_TOKEN:-$SLACK_BOT_TOKEN}")
      if [ -n "$TRAW" ] && ! printf '%s' "$TRAW" | head -c 300 | grep -qi '<!DOCTYPE html\|<html'; then
        TCONTENT=$(printf '%s' "$TRAW" | sed 's/<[^>]*>//g; /^[[:space:]]*$/d')
        [ -s /tmp/huddle-users.sed ] && TCONTENT=$(printf '%s' "$TCONTENT" | sed -f /tmp/huddle-users.sed)
        {
          printf -- '---\n'
          printf 'date: %s\n' "$FDATE"
          printf 'source: slack-huddle-full-transcript\n'
          printf 'channel: "%s"\n' "$channel"
          printf 'slack_file_id: "%s"\n' "$TR_ID"
          printf 'archived_by: pm-huddle-notes\n'
          printf -- '---\n\n'
          printf '# :studio_microphone: Full transcript — #%s — %s\n\n' "$channel" "$FDATE"
          printf '%s\n' "$TCONTENT"
        } > /tmp/huddle-upload.md
        if [ "$(vault_put "$TDEST" "huddle: $FDATE #$channel — full transcript archived by pm-huddle-notes")" = "OK" ]; then
          WRITTEN=$((WRITTEN+1))
          echo "WRITE: $DIR/transcript.md" >> /tmp/huddle-log.txt
        else
          ERRORS=$((ERRORS+1))
        fi
      else
        echo "INFO: transcript $TR_ID not downloadable with current token (Slack gates huddle_transcript files; permalink recorded in notes.md)" >> /tmp/huddle-log.txt
      fi
    fi
  fi

  sleep 0.3
done < /tmp/huddle-files.tsv

echo "=== Summary ===" >> /tmp/huddle-log.txt
echo "Scanned: $ITER | Written: $WRITTEN | Skipped: $SKIPPED | Errors: $ERRORS" >> /tmp/huddle-log.txt
cat /tmp/huddle-log.txt
```
