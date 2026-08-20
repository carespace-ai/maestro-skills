# Step 5: Collect Huddle Threads → /tmp/huddle-threads.tsv

Every huddle held in a channel leaves a `huddle_thread` message anchoring a thread that
holds everything said/posted during the huddle — including Slack AI huddle-notes posts.
This step finds those anchors within the lookback window, and builds a user-ID→name map
for transcript rendering.

> Note: Slack's public API does not expose the raw **audio** transcript of a huddle.
> What we archive is the huddle thread: all messages posted in it (chat, links, AI notes).
> The AI-notes canvas itself is archived by Steps 2/4.

```bash
source ~/.claude/skills/_pm-shared/context.sh
OLDEST=$(( $(date +%s) - HUDDLE_LOOKBACK_DAYS * 86400 ))
> /tmp/huddle-threads.tsv   # channel<TAB>ch_id<TAB>thread_ts<TAB>started_ts<TAB>participants

for ch in $HUDDLE_SOURCE_CHANNELS; do
  CH_ID=$(awk -F'\t' -v n="$ch" '$1==n{print $2}' /tmp/huddle-channels.tsv)
  [ -z "$CH_ID" ] && echo "SKIP: #$ch (no ID — see Step 1 blockers)" && continue

  RESP=$(curl -s "https://slack.com/api/conversations.history?channel=${CH_ID}&oldest=${OLDEST}&limit=200" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  if [ "$(echo "$RESP" | jq -r '.ok')" != "true" ]; then
    echo "BLOCKER: conversations.history #$ch → $(echo "$RESP" | jq -r '.error')" \
      | tee -a /tmp/huddle-blockers.txt
    continue
  fi

  echo "$RESP" | jq -r --arg ch "$ch" --arg id "$CH_ID" '
      .messages[]?
      | select(.subtype == "huddle_thread")
      | [$ch, $id, .ts,
         ((.room.created // (.ts | tonumber | floor)) | tostring),
         ((.room.participant_history // .room.participants // []) | join(","))]
      | @tsv
    ' >> /tmp/huddle-threads.tsv

  sleep 0.3
done

echo "Huddle threads found: $(wc -l < /tmp/huddle-threads.tsv)"

# ── User map for name resolution in transcripts ──────────────────────
> /tmp/huddle-users.tsv   # user_id<TAB>display_name
CURSOR=""
while true; do
  URL="https://slack.com/api/users.list?limit=200"
  [ -n "$CURSOR" ] && URL="${URL}&cursor=${CURSOR}"
  PAGE=$(curl -s "$URL" -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  [ "$(echo "$PAGE" | jq -r '.ok')" != "true" ] && \
    echo "WARN: users.list → $(echo "$PAGE" | jq -r '.error') — transcripts will show raw IDs" && break
  echo "$PAGE" | jq -r '
      .members[]?
      | [.id, (((.profile.display_name // "") | if . == "" then null else . end)
               // .real_name // .name)]
      | @tsv
    ' >> /tmp/huddle-users.tsv
  CURSOR=$(echo "$PAGE" | jq -r '.response_metadata.next_cursor // empty')
  [ -z "$CURSOR" ] && break
  sleep 0.3
done
echo "Users mapped: $(wc -l < /tmp/huddle-users.tsv)"
```
