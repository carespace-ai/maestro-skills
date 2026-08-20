# Step 1: Resolve Channel IDs → /tmp/huddle-channels.tsv

`files.list` and `conversations.history` require channel IDs, not names.
Paginate `conversations.list` to handle workspaces with >200 channels.
Note: private channels only appear if the bot is a **member** (plus `groups:read`).

```bash
source ~/.claude/skills/_pm-shared/context.sh
> /tmp/huddle-channels.tsv   # name<TAB>id

CURSOR=""
while true; do
  URL="https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200"
  [ -n "$CURSOR" ] && URL="${URL}&cursor=${CURSOR}"

  PAGE=$(curl -s "$URL" -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  if [ "$(echo "$PAGE" | jq -r '.ok')" != "true" ]; then
    echo "FATAL: conversations.list failed → $(echo "$PAGE" | jq -r '.error')"
    exit 1
  fi
  echo "$PAGE" | jq -r '.channels[] | [.name, .id] | @tsv' >> /tmp/huddle-channels.tsv

  CURSOR=$(echo "$PAGE" | jq -r '.response_metadata.next_cursor // empty')
  [ -z "$CURSOR" ] && break
  sleep 0.3
done

# Verify all source channels resolved — unresolved is a hard error, not a silent skip
UNRESOLVED=0
for ch in $HUDDLE_SOURCE_CHANNELS; do
  ID=$(awk -F'\t' -v n="$ch" '$1==n{print $2}' /tmp/huddle-channels.tsv)
  if [ -z "$ID" ]; then
    UNRESOLVED=$((UNRESOLVED+1))
    echo "BLOCKER: channel '$ch' not visible to the bot."
    echo "  If #$ch is private: the bot must be a member — run /invite @<bot> in #$ch"
    echo "  (groups:read alone is not enough; private channels list only for members)."
    echo "  If #$ch is public: check the exact channel name."
  else
    echo "Resolved: #$ch → $ID"
  fi
done

if [ "$UNRESOLVED" -eq "$(echo $HUDDLE_SOURCE_CHANNELS | wc -w)" ]; then
  echo "FATAL: no source channel could be resolved — nothing to collect. Aborting."
  exit 1
fi

# ── User map (user_id → display name) for name resolution in notes/transcripts ──
# Degrades gracefully: without users:read, content keeps raw U-IDs.
> /tmp/huddle-users.tsv   # user_id<TAB>display_name
CURSOR=""
while true; do
  URL="https://slack.com/api/users.list?limit=200"
  [ -n "$CURSOR" ] && URL="${URL}&cursor=${CURSOR}"
  PAGE=$(curl -s "$URL" -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  [ "$(echo "$PAGE" | jq -r '.ok')" != "true" ] && \
    echo "WARN: users.list → $(echo "$PAGE" | jq -r '.error') — archived content will show raw user IDs" && break
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

# sed script for substituting raw U-IDs with names in canvas/transcript text
# (| \ & stripped from names so they can't break the sed expression)
awk -F'\t' 'NF>=2 {n=$2; gsub(/[|\\&]/, "", n); print "s|" $1 "|" n "|g"}' \
  /tmp/huddle-users.tsv > /tmp/huddle-users.sed

# sed script for substituting channel IDs with channel names (e.g. canvas titles)
awk -F'\t' 'NF>=2 {n=$1; gsub(/[|\\&]/, "", n); print "s|" $2 "|" n "|g"}' \
  /tmp/huddle-channels.tsv > /tmp/huddle-channels.sed
```
