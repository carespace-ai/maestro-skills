# Step 5: Archive Huddle Threads → <huddle-folder>/thread.md + /tmp/huddle-log.txt

For each huddle thread collected in Step 2: fetch all thread replies via `conversations.replies`,
render a markdown transcript of the thread (bulleted, timestamped, usernames resolved),
and write it as `thread.md` inside the same per-huddle folder Step 4 uses — the folder
name derives from the thread's start ts (UTC), so notes and thread pair automatically.

```bash
source ~/.claude/skills/_pm-shared/context.sh
TWRITTEN=0; TSKIPPED=0; TERRORS=0; MAX=$HUDDLE_MAX_PER_RUN

# user_id → name lookup as a jq object
UMAP=$(jq -Rn '[inputs | split("\t") | select(length >= 2) | {(.[0]): .[1]}] | add // {}' \
  < /tmp/huddle-users.tsv 2>/dev/null || echo '{}')

while IFS=$'\t' read -r channel ch_id thread_ts started participants; do
  [ -z "$thread_ts" ] && continue
  [ $TWRITTEN -ge $MAX ] && echo "HIT MAX $MAX thread writes — stopping" >> /tmp/huddle-log.txt && break

  EPOCH=${thread_ts%%.*}
  # -u: folder names must be timezone-independent (UTC) so every runner agrees
  FDATE=$(date -u -d "@$EPOCH" +%Y-%m-%d 2>/dev/null || echo "unknown")
  FTIME=$(date -u -d "@$EPOCH" +%H%M       2>/dev/null || echo "0000")
  DIR="${FDATE}-${FTIME}-${channel}"
  DEST="$HUDDLE_VAULT_PATH/$DIR/thread.md"

  # Idempotency: skip if thread.md already exists in this huddle's folder
  if gh api "repos/$HUDDLE_VAULT_REPO/contents/$DEST" --jq '.sha' >/dev/null 2>&1; then
    TSKIPPED=$((TSKIPPED+1))
    echo "SKIP (exists): $DIR/thread.md" >> /tmp/huddle-log.txt
    continue
  fi

  REPLIES=$(curl -s "https://slack.com/api/conversations.replies?channel=${ch_id}&ts=${thread_ts}&limit=200" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  if [ "$(echo "$REPLIES" | jq -r '.ok')" != "true" ]; then
    TERRORS=$((TERRORS+1))
    echo "ERROR: conversations.replies $thread_ts → $(echo "$REPLIES" | jq -r '.error')" >> /tmp/huddle-log.txt
    continue
  fi

  # Bulleted markdown lines: "- **[HH:MM] name:** text" — skip empty messages,
  # resolve inline <@U...> mentions, list attached files
  CONTENT=$(echo "$REPLIES" | jq -r --argjson u "$UMAP" '
      .messages[]?
      | select((.text // "") != "" or ((.files // []) | length) > 0)
      | "- **[" + (.ts | tonumber | floor | strftime("%H:%M")) + "] "
        + ($u[.user // ""] // .user // (.bot_profile.name // "bot")) + ":** "
        + ((.text // "") | gsub("<@(?<id>U[A-Z0-9]+)>"; "@" + ($u[.id] // .id)))
        + (if ((.files // []) | length) > 0
           then " _[files: " + ((.files // []) | map(.name // .id) | join(", ")) + "]_"
           else "" end)
    ')

  CLEN=${#CONTENT}
  if [ "$CLEN" -lt "$HUDDLE_MIN_CONTENT_CHARS" ]; then
    TSKIPPED=$((TSKIPPED+1))
    echo "SKIP (thin ${CLEN}c): $DIR/thread.md" >> /tmp/huddle-log.txt
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
    printf 'source: slack-huddle-thread\n'
    printf 'channel: "%s"\n' "$channel"
    printf 'huddle_thread_ts: "%s"\n' "$thread_ts"
    printf 'participants: "%s"\n' "$PNAMES"
    printf 'archived_by: pm-huddle-notes\n'
    printf -- '---\n\n'
    printf '# :speech_balloon: Huddle thread — #%s — %s %s UTC\n\n' "$channel" "$FDATE" "$FTIME"
    printf '**Participants:** %s\n\n' "$PNAMES"
    printf '%s\n' "$CONTENT"
  } > /tmp/huddle-upload.md

  B64=$(base64 -w0 /tmp/huddle-upload.md)
  PAYLOAD=$(jq -n \
    --arg msg "huddle: $FDATE #$channel — thread archived by pm-huddle-notes" \
    --arg content "$B64" \
    '{message: $msg, content: $content}')
  RESULT=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$DEST" \
    -X PUT --input - <<< "$PAYLOAD" \
    --jq '.content.name // "ERROR"' 2>&1)

  if [ "$RESULT" = "ERROR" ] || echo "$RESULT" | grep -q '"message"'; then
    TERRORS=$((TERRORS+1))
    echo "ERROR: $DIR/thread.md → $RESULT" >> /tmp/huddle-log.txt
  else
    TWRITTEN=$((TWRITTEN+1))
    echo "WRITE: $DIR/thread.md (${CLEN}c)" >> /tmp/huddle-log.txt
  fi

  sleep 0.3
done < /tmp/huddle-threads.tsv

echo "=== Thread Summary ===" >> /tmp/huddle-log.txt
echo "Threads written: $TWRITTEN | Skipped: $TSKIPPED | Errors: $TERRORS" >> /tmp/huddle-log.txt
tail -20 /tmp/huddle-log.txt
```
