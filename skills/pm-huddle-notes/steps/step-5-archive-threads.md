# Step 5: Archive Huddle Conversations → <huddle-folder>/thread.md + /tmp/huddle-log.txt

`thread.md` is the huddle's CONVERSATION file, with two sections:

1. **Transcript** — the full spoken transcript. Slack only serves
   `huddle_transcript` files to user tokens (`SLACK_USER_TOKEN`); with a bot
   token this section carries the Slack link and a "pending" marker instead.
2. **Thread messages** — everything typed in the huddle thread.

Upgrade-in-place: if an existing `thread.md` has a pending transcript and the
transcript is now downloadable, the file is rewritten (sha update). Otherwise
existing files are skipped (idempotent).

Transcript source: `/tmp/huddle-transcripts.tsv` from Step 4; falls back to the
`transcript_file_id` recorded in the folder's `notes.md` frontmatter.

```bash
source ~/.claude/skills/_pm-shared/context.sh
TWRITTEN=0; TSKIPPED=0; TERRORS=0; MAX=$HUDDLE_MAX_PER_RUN
PENDING_MARK='transcript pending'

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

  # ── Transcript lookup: Step 4 map → notes.md frontmatter fallback ──
  TR_ID=""; TR_PERMALINK=""; TR_DL=""
  TRLINE=$(awk -F'\t' -v d="$DIR" '$1==d{print; exit}' /tmp/huddle-transcripts.tsv 2>/dev/null)
  if [ -n "$TRLINE" ]; then
    TR_ID=$(echo "$TRLINE" | cut -f2)
    TR_PERMALINK=$(echo "$TRLINE" | cut -f3)
    TR_DL=$(echo "$TRLINE" | cut -f4)
  else
    TR_ID=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$HUDDLE_VAULT_PATH/$DIR/notes.md" \
      --jq '.content' 2>/dev/null | base64 -d 2>/dev/null \
      | grep -m1 '^transcript_file_id:' | sed 's/.*"\(.*\)"/\1/')
    if [ -n "$TR_ID" ]; then
      TINFO=$(curl -s "https://slack.com/api/files.info?file=${TR_ID}" \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN")
      TR_PERMALINK=$(echo "$TINFO" | jq -r '.file.permalink // ""')
      TR_DL=$(echo "$TINFO" | jq -r '.file.url_private_download // .file.url_private // ""')
    fi
  fi

  # ── Try to download the full transcript ──
  # Slack hard-blocks huddle_transcript downloads for ALL OAuth tokens (bot and
  # user; verified 2026-08-20: CDN 302s to login, files.sharedPublicURL returns
  # not_allowed for this filetype only). The ONLY credential Slack serves them
  # to is a web-session cookie — set SLACK_COOKIE_D (the `d` cookie value,
  # xoxd-...) as a runner secret. Falls back to token auth in case Slack ever
  # opens it up.
  TCONTENT=""
  if [ -n "$TR_DL" ]; then
    if [ -n "${SLACK_COOKIE_D:-}" ]; then
      TRAW=$(curl -sL "$TR_DL" -H "Cookie: d=${SLACK_COOKIE_D}")
    else
      TRAW=$(curl -sL "$TR_DL" -H "Authorization: Bearer ${SLACK_USER_TOKEN:-$SLACK_BOT_TOKEN}")
    fi
    if [ -n "$TRAW" ] && ! printf '%s' "$TRAW" | head -c 300 | grep -qi '<!DOCTYPE html\|<html'; then
      if printf '%s' "$TRAW" | jq . >/dev/null 2>&1; then
        TCONTENT=$(printf '%s' "$TRAW" | jq -r '.. | .text? // empty' 2>/dev/null | grep -v '^$')
      else
        TCONTENT=$(printf '%s' "$TRAW" | sed 's/<[^>]*>//g; /^[[:space:]]*$/d')
      fi
      [ -s /tmp/huddle-users.sed ] && TCONTENT=$(printf '%s' "$TCONTENT" | sed -f /tmp/huddle-users.sed)
    fi
  fi

  # ── Idempotency / upgrade decision ──
  EXISTING=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$DEST" --jq '.content' 2>/dev/null \
    | base64 -d 2>/dev/null || echo "")
  if [ -n "$EXISTING" ]; then
    if echo "$EXISTING" | grep -q "$PENDING_MARK" && [ -n "$TCONTENT" ]; then
      echo "UPGRADE: $DIR/thread.md (transcript now available)" >> /tmp/huddle-log.txt
    else
      TSKIPPED=$((TSKIPPED+1))
      echo "SKIP (exists): $DIR/thread.md" >> /tmp/huddle-log.txt
      continue
    fi
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
  THREADMSGS=$(echo "$REPLIES" | jq -r --argjson u "$UMAP" '
      .messages[]?
      | select((.text // "") != "" or ((.files // []) | length) > 0)
      | "- **[" + (.ts | tonumber | floor | strftime("%H:%M")) + "] "
        + ($u[.user // ""] // .user // (.bot_profile.name // "bot")) + ":** "
        + ((.text // "") | gsub("<@(?<id>U[A-Z0-9]+)>"; "@" + ($u[.id] // .id)))
        + (if ((.files // []) | length) > 0
           then " _[files: " + ((.files // []) | map(.name // .id) | join(", ")) + "]_"
           else "" end)
    ')

  CLEN=$(( ${#THREADMSGS} + ${#TCONTENT} ))
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
    printf 'source: slack-huddle-conversation\n'
    printf 'channel: "%s"\n' "$channel"
    printf 'huddle_thread_ts: "%s"\n' "$thread_ts"
    printf 'participants: "%s"\n' "$PNAMES"
    [ -n "$TR_ID" ] && printf 'transcript_file_id: "%s"\n' "$TR_ID"
    [ -n "$TR_PERMALINK" ] && printf 'transcript_url: "%s"\n' "$TR_PERMALINK"
    printf 'archived_by: pm-huddle-notes\n'
    printf -- '---\n\n'
    printf '# :speech_balloon: Huddle conversation — #%s — %s %s UTC\n\n' "$channel" "$FDATE" "$FTIME"
    printf '**Participants:** %s\n\n' "$PNAMES"
    printf '## :studio_microphone: Transcript\n\n'
    if [ -n "$TCONTENT" ]; then
      printf '%s\n\n' "$TCONTENT"
    elif [ -n "$TR_PERMALINK" ]; then
      printf '_Full transcript pending — Slack only serves huddle transcripts to web-session credentials; set `SLACK_COOKIE_D` on the runner to archive it here automatically. [Open transcript in Slack](%s)_\n\n' "$TR_PERMALINK"
    else
      printf '_No transcript file found for this huddle._\n\n'
    fi
    printf '## :thread: Thread messages\n\n'
    if [ -n "$THREADMSGS" ]; then
      printf '%s\n' "$THREADMSGS"
    else
      printf '_No messages were posted in the huddle thread._\n'
    fi
  } > /tmp/huddle-upload.md

  B64=$(base64 -w0 /tmp/huddle-upload.md)
  SHA=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$DEST" --jq '.sha' 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(jq -n \
      --arg msg "huddle: $FDATE #$channel — conversation upgraded with full transcript" \
      --arg content "$B64" --arg sha "$SHA" \
      '{message: $msg, content: $content, sha: $sha}')
  else
    PAYLOAD=$(jq -n \
      --arg msg "huddle: $FDATE #$channel — conversation archived by pm-huddle-notes" \
      --arg content "$B64" \
      '{message: $msg, content: $content}')
  fi
  RESULT=$(gh api "repos/$HUDDLE_VAULT_REPO/contents/$DEST" \
    -X PUT --input - <<< "$PAYLOAD" \
    --jq '.content.name // "ERROR"' 2>&1)

  if [ "$RESULT" = "ERROR" ] || echo "$RESULT" | grep -q '"message"'; then
    TERRORS=$((TERRORS+1))
    echo "ERROR: $DIR/thread.md → $RESULT" >> /tmp/huddle-log.txt
  else
    TWRITTEN=$((TWRITTEN+1))
    echo "WRITE: $DIR/thread.md (${CLEN}c, transcript: $([ -n "$TCONTENT" ] && echo embedded || echo pending))" >> /tmp/huddle-log.txt
  fi

  sleep 0.3
done < /tmp/huddle-threads.tsv

echo "=== Conversation Summary ===" >> /tmp/huddle-log.txt
echo "Written: $TWRITTEN | Skipped: $TSKIPPED | Errors: $TERRORS" >> /tmp/huddle-log.txt
tail -20 /tmp/huddle-log.txt
```
