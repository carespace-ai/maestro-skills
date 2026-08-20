# Step 4: Download + Archive New Huddles → /tmp/huddle-log.txt

Downloads canvas content via `url_private`, strips to plaintext, writes to vault.
Uses sha-based GitHub PUT — safe if file already exists (updates instead of erroring).
Filename collision on same-minute huddles resolved with file_id suffix.

```bash
source ~/.claude/skills/_pm-shared/context.sh
> /tmp/huddle-log.txt
WRITTEN=0; SKIPPED=0; ERRORS=0; ITER=0; MAX=$HUDDLE_MAX_PER_RUN

while IFS=$'\t' read -r channel file_id created_ts name url_private; do
  [ $WRITTEN -ge $MAX ] && echo "HIT MAX $MAX writes — stopping" >> /tmp/huddle-log.txt && break
  ITER=$((ITER+1))

  # -u: filenames must be timezone-independent (UTC) so every runner agrees
  FDATE=$(date -u -d "@$created_ts" +%Y-%m-%d 2>/dev/null || echo "unknown")
  FTIME=$(date -u -d "@$created_ts" +%H%M       2>/dev/null || echo "0000")
  # Include file_id suffix to prevent same-minute collisions
  FNAME="${FDATE}-${FTIME}-${file_id}.md"

  # Skip if already in vault — match on the immutable Slack file ID, NOT the
  # full filename: the HHMM part is rendered in the runner's local timezone,
  # so name-based matching would duplicate files across differently-zoned runners
  if grep -qF "$file_id" /tmp/vault-existing.txt 2>/dev/null; then
    SKIPPED=$((SKIPPED+1))
    echo "SKIP (exists): $FNAME" >> /tmp/huddle-log.txt
    continue
  fi

  # Skip if no URL
  if [ -z "$url_private" ]; then
    SKIPPED=$((SKIPPED+1))
    echo "SKIP (no url): $name" >> /tmp/huddle-log.txt
    continue
  fi

  # Download raw canvas content
  RAW=$(curl -sL "$url_private" -H "Authorization: Bearer $SLACK_BOT_TOKEN")

  # Strip HTML tags to plaintext if content looks like HTML.
  # NOTE: canvas exports start with <div class="quip-canvas-content"> — no
  # <html>/<!DOCTYPE — so detect ANY opening tag, not just document headers
  # (the old check silently archived raw HTML). Block-level closers become
  # newlines first so the plaintext keeps its structure.
  if echo "$RAW" | grep -q '<[a-zA-Z][^>]*>'; then
    CONTENT=$(printf '%s' "$RAW" \
      | sed 's#</p>#\n#g; s#</li>#\n#g; s#</h[1-6]>#\n\n#g; s#<br/>#\n#g; s#<hr[^>]*>#\n---\n#g' \
      | sed 's/<[^>]*>//g; /^[[:space:]]*$/d' \
      | sed 's/&amp;/\&/g; s/&lt;/</g; s/&gt;/>/g; s/&nbsp;/ /g; s/&#39;/'"'"'/g')
  elif echo "$RAW" | jq . >/dev/null 2>&1; then
    # JSON canvas format — extract text blocks
    CONTENT=$(echo "$RAW" | jq -r '
      .. | objects | select(.type == "text" or .type == "rich_text")
         | (.text // .elements // []) | if type == "array" then .[].text? // "" else . end
    ' 2>/dev/null | grep -v '^$')
  else
    # Already plaintext
    CONTENT="$RAW"
  fi

  # Substitute raw Slack user IDs with display names (map built in Step 1;
  # no-op when users:read is missing)
  [ -s /tmp/huddle-users.sed ] && CONTENT=$(printf '%s' "$CONTENT" | sed -f /tmp/huddle-users.sed)

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

  # Build vault file (use printf to avoid heredoc HEOF collision)
  {
    printf -- '---\n'
    printf 'date: %s\n' "$FDATE"
    printf 'source: slack-huddle\n'
    printf 'channel: "%s"\n' "$channel"
    printf 'slack_file_id: "%s"\n' "$file_id"
    [ -n "$TR_ID" ] && printf 'transcript_file_id: "%s"\n' "$TR_ID"
    [ -n "$TR_PERMALINK" ] && printf 'transcript_url: "%s"\n' "$TR_PERMALINK"
    printf 'archived_by: pm-huddle-notes\n'
    printf -- '---\n\n'
    printf '%s\n' "$CONTENT"
  } > /tmp/huddle-upload.md

  B64=$(base64 -w0 /tmp/huddle-upload.md)

  # Check if file exists in vault to get sha (required for update)
  EXISTING_SHA=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$HUDDLE_VAULT_PATH/$FNAME" \
    --jq '.sha' 2>/dev/null || echo "")

  # Build PUT payload
  if [ -n "$EXISTING_SHA" ]; then
    PAYLOAD=$(jq -n \
      --arg msg "huddle: $FDATE from #$channel — updated by pm-huddle-notes" \
      --arg content "$B64" \
      --arg sha "$EXISTING_SHA" \
      '{message: $msg, content: $content, sha: $sha}')
  else
    PAYLOAD=$(jq -n \
      --arg msg "huddle: $FDATE from #$channel — archived by pm-huddle-notes" \
      --arg content "$B64" \
      '{message: $msg, content: $content}')
  fi

  RESULT=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$HUDDLE_VAULT_PATH/$FNAME" \
    -X PUT --input - <<< "$PAYLOAD" \
    --jq '.content.name // "ERROR"' 2>&1)

  if [ "$RESULT" = "ERROR" ] || echo "$RESULT" | grep -q '"message"'; then
    ERRORS=$((ERRORS+1))
    echo "ERROR: $FNAME → $RESULT" >> /tmp/huddle-log.txt
  else
    WRITTEN=$((WRITTEN+1))
    echo "WRITE: $FNAME (#$channel, ${CLEN}c)" >> /tmp/huddle-log.txt
  fi

  # Best-effort full transcript archive (works only with a token Slack lets
  # download huddle_transcript files — currently NOT bot tokens)
  if [ -n "$TR_ID" ] && [ -n "$TR_DL" ]; then
    TNAME="${FDATE}-${FTIME}-${TR_ID}-fulltranscript.md"
    # ID-based skip check (timezone-safe, same rationale as above)
    if grep -qF "$TR_ID" /tmp/vault-existing.txt 2>/dev/null; then
      echo "SKIP (exists): $TNAME" >> /tmp/huddle-log.txt
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
          printf '%s\n' "$TCONTENT"
        } > /tmp/huddle-upload.md
        B64=$(base64 -w0 /tmp/huddle-upload.md)
        TSHA=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$HUDDLE_VAULT_PATH/$TNAME" --jq '.sha' 2>/dev/null || echo "")
        if [ -n "$TSHA" ]; then
          TPAYLOAD=$(jq -n --arg msg "huddle full transcript: $FDATE from #$channel" --arg content "$B64" --arg sha "$TSHA" '{message: $msg, content: $content, sha: $sha}')
        else
          TPAYLOAD=$(jq -n --arg msg "huddle full transcript: $FDATE from #$channel" --arg content "$B64" '{message: $msg, content: $content}')
        fi
        TRESULT=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$HUDDLE_VAULT_PATH/$TNAME" \
          -X PUT --input - <<< "$TPAYLOAD" --jq '.content.name // "ERROR"' 2>&1)
        if [ "$TRESULT" = "ERROR" ] || echo "$TRESULT" | grep -q '"message"'; then
          echo "ERROR: $TNAME → $TRESULT" >> /tmp/huddle-log.txt
        else
          WRITTEN=$((WRITTEN+1))
          echo "WRITE: $TNAME (full transcript)" >> /tmp/huddle-log.txt
        fi
      else
        echo "INFO: transcript $TR_ID not downloadable with current token (Slack gates huddle_transcript files; permalink recorded in $FNAME)" >> /tmp/huddle-log.txt
      fi
    fi
  fi

  sleep 0.3
done < /tmp/huddle-files.tsv

echo "=== Summary ===" >> /tmp/huddle-log.txt
echo "Scanned: $ITER | Written: $WRITTEN | Skipped: $SKIPPED | Errors: $ERRORS" >> /tmp/huddle-log.txt
cat /tmp/huddle-log.txt
```
