# Step 2: Collect Canvas Files → /tmp/huddle-files.tsv

Scan each source channel's file list for canvas/quip files within the lookback window.
Uses `files.list` (still works for canvas files attached to messages) with proper timestamp params.
Falls back to scanning `conversations.history` for huddle-generated canvas links if `files.list` returns 0.

**Every API error is logged to /tmp/huddle-blockers.txt with a concrete fix — never silently swallowed.**

```bash
source ~/.claude/skills/_pm-shared/context.sh
OLDEST=$(( $(date +%s) - HUDDLE_LOOKBACK_DAYS * 86400 ))
> /tmp/huddle-files.tsv   # channel<TAB>file_id<TAB>created_ts<TAB>name<TAB>url_private
> /tmp/huddle-blockers.txt

log_blocker() {  # $1=api $2=channel $3=error
  echo "BLOCKER: $1 #$2 → $3" | tee -a /tmp/huddle-blockers.txt
  case "$3" in
    missing_scope)  echo "  Fix: add the required scope (see Step 0 list) + reinstall the Slack app" | tee -a /tmp/huddle-blockers.txt ;;
    not_in_channel) echo "  Fix: run /invite @<bot> in #$2" | tee -a /tmp/huddle-blockers.txt ;;
  esac
}

for ch in $HUDDLE_SOURCE_CHANNELS; do
  CH_ID=$(awk -F'\t' -v n="$ch" '$1==n{print $2}' /tmp/huddle-channels.tsv)
  [ -z "$CH_ID" ] && echo "SKIP: #$ch (no ID — see Step 1 blockers)" && continue

  # Primary: files.list for canvas/quip types
  RESP=$(curl -s "https://slack.com/api/files.list?channel=${CH_ID}&ts_from=${OLDEST}&types=spaces.canvas,canvas,quip&count=50" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  if [ "$(echo "$RESP" | jq -r '.ok')" != "true" ]; then
    log_blocker "files.list" "$ch" "$(echo "$RESP" | jq -r '.error')"
  else
    echo "$RESP" | jq -r --arg ch "$ch" \
        '.files[]? | [$ch, .id, (.created|tostring), (.name // "huddle-note"), (.url_private // "")] | @tsv' \
      >> /tmp/huddle-files.tsv
  fi

  # Fallback: scan message history for canvas attachments (huddle auto-generated notes)
  RESP=$(curl -s "https://slack.com/api/conversations.history?channel=${CH_ID}&oldest=${OLDEST}&limit=100" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  if [ "$(echo "$RESP" | jq -r '.ok')" != "true" ]; then
    log_blocker "conversations.history" "$ch" "$(echo "$RESP" | jq -r '.error')"
  else
    echo "$RESP" | jq -r --arg ch "$ch" '
        .messages[]?
        | select(.files? or .attachments?)
        | (.files // [])[]
        | select(.filetype == "canvas" or .filetype == "spaces_canvas" or .filetype == "quip")
        | [$ch, .id, (.created|tostring), (.name // "huddle-note"), (.url_private // "")]
        | @tsv
      ' >> /tmp/huddle-files.tsv 2>/dev/null
  fi

  sleep 0.3
done

# Deduplicate by file_id (same file may appear in both queries)
sort -t$'\t' -k2,2 -u /tmp/huddle-files.tsv > /tmp/huddle-files-dedup.tsv
mv /tmp/huddle-files-dedup.tsv /tmp/huddle-files.tsv

echo "Canvas files found: $(wc -l < /tmp/huddle-files.tsv)"
awk -F'\t' '{print $1, $4}' /tmp/huddle-files.tsv

# Zero files AND blockers present = the run is broken, not "quiet" — fail loudly
if [ ! -s /tmp/huddle-files.tsv ] && [ -s /tmp/huddle-blockers.txt ]; then
  echo "FATAL: 0 canvas files collected and API blockers were hit:"
  cat /tmp/huddle-blockers.txt
  echo "Fix the blockers above, then re-run (idempotent)."
  exit 1
fi
```
