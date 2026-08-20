# Step 6: Archive Huddle Transcripts → vault + /tmp/huddle-log.txt

For each huddle thread from Step 5: fetch all thread replies via `conversations.replies`,
render a timestamped transcript with resolved usernames, and write it to the vault.
Same idempotency + sha-based PUT rules as Step 4. Filename embeds the thread ts, so
re-runs skip already-archived huddles.

```bash
source ~/.claude/skills/_pm-shared/context.sh
TWRITTEN=0; TSKIPPED=0; TERRORS=0; MAX=$HUDDLE_MAX_PER_RUN

# user_id → name lookup as a jq object
UMAP=$(jq -Rn '[inputs | split("\t") | select(length >= 2) | {(.[0]): .[1]}] | add // {}' \
  < /tmp/huddle-users.tsv 2>/dev/null || echo '{}')

while IFS=$'\t' read -r channel ch_id thread_ts started participants; do
  [ -z "$thread_ts" ] && continue
  [ $TWRITTEN -ge $MAX ] && echo "HIT MAX $MAX transcript writes — stopping" >> /tmp/huddle-log.txt && break

  EPOCH=${started%%.*}
  FDATE=$(date -d "@$EPOCH" +%Y-%m-%d 2>/dev/null || echo "unknown")
  FTIME=$(date -d "@$EPOCH" +%H%M       2>/dev/null || echo "0000")
  TSID=$(echo "$thread_ts" | tr '.' '-')
  FNAME="${FDATE}-${FTIME}-huddle-${TSID}-transcript.md"

  if grep -qF "$FNAME" /tmp/vault-existing.txt 2>/dev/null; then
    TSKIPPED=$((TSKIPPED+1))
    echo "SKIP (exists): $FNAME" >> /tmp/huddle-log.txt
    continue
  fi

  REPLIES=$(curl -s "https://slack.com/api/conversations.replies?channel=${ch_id}&ts=${thread_ts}&limit=200" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  if [ "$(echo "$REPLIES" | jq -r '.ok')" != "true" ]; then
    TERRORS=$((TERRORS+1))
    echo "ERROR: conversations.replies $thread_ts → $(echo "$REPLIES" | jq -r '.error')" >> /tmp/huddle-log.txt
    continue
  fi

  # Timestamped lines: "[HH:MM] name: text" — skip empty-text messages, list any files
  CONTENT=$(echo "$REPLIES" | jq -r --argjson u "$UMAP" '
      .messages[]?
      | select((.text // "") != "" or ((.files // []) | length) > 0)
      | "[" + (.ts | tonumber | floor | strftime("%H:%M")) + "] "
        + ($u[.user // ""] // .user // (.bot_profile.name // "bot")) + ": "
        + (.text // "")
        + (if ((.files // []) | length) > 0
           then " [files: " + ((.files // []) | map(.name // .id) | join(", ")) + "]"
           else "" end)
    ')

  CLEN=${#CONTENT}
  if [ "$CLEN" -lt "$HUDDLE_MIN_CONTENT_CHARS" ]; then
    TSKIPPED=$((TSKIPPED+1))
    echo "SKIP (thin ${CLEN}c): $FNAME" >> /tmp/huddle-log.txt
    continue
  fi

  # Resolve participant names for frontmatter
  PNAMES=$(echo "$participants" | tr ',' '\n' | while read -r uid; do
    [ -z "$uid" ] && continue
    awk -F'\t' -v id="$uid" '$1==id{print $2; found=1} END{if(!found) print id}' /tmp/huddle-users.tsv
  done | paste -sd, - | sed 's/,/, /g')

  {
    printf -- '---\n'
    printf 'date: %s\n' "$FDATE"
    printf 'source: slack-huddle-transcript\n'
    printf 'channel: "%s"\n' "$channel"
    printf 'huddle_thread_ts: "%s"\n' "$thread_ts"
    printf 'participants: "%s"\n' "$PNAMES"
    printf 'archived_by: pm-huddle-notes\n'
    printf -- '---\n\n'
    printf '# Huddle transcript — #%s — %s %s\n\n' "$channel" "$FDATE" "$FTIME"
    printf '%s\n' "$CONTENT"
  } > /tmp/huddle-transcript.md

  B64=$(base64 -w0 /tmp/huddle-transcript.md)
  EXISTING_SHA=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$HUDDLE_VAULT_PATH/$FNAME" \
    --jq '.sha' 2>/dev/null || echo "")

  if [ -n "$EXISTING_SHA" ]; then
    PAYLOAD=$(jq -n \
      --arg msg "huddle transcript: $FDATE from #$channel — updated by pm-huddle-notes" \
      --arg content "$B64" --arg sha "$EXISTING_SHA" \
      '{message: $msg, content: $content, sha: $sha}')
  else
    PAYLOAD=$(jq -n \
      --arg msg "huddle transcript: $FDATE from #$channel — archived by pm-huddle-notes" \
      --arg content "$B64" \
      '{message: $msg, content: $content}')
  fi

  RESULT=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$HUDDLE_VAULT_PATH/$FNAME" \
    -X PUT --input - <<< "$PAYLOAD" \
    --jq '.content.name // "ERROR"' 2>&1)

  if [ "$RESULT" = "ERROR" ] || echo "$RESULT" | grep -q '"message"'; then
    TERRORS=$((TERRORS+1))
    echo "ERROR: $FNAME → $RESULT" >> /tmp/huddle-log.txt
  else
    TWRITTEN=$((TWRITTEN+1))
    echo "WRITE: $FNAME (#$channel, ${CLEN}c transcript)" >> /tmp/huddle-log.txt
  fi

  sleep 0.3
done < /tmp/huddle-threads.tsv

echo "=== Transcript Summary ===" >> /tmp/huddle-log.txt
echo "Transcripts written: $TWRITTEN | Skipped: $TSKIPPED | Errors: $TERRORS" >> /tmp/huddle-log.txt
tail -20 /tmp/huddle-log.txt
```
