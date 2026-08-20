# Step 0: Load Shared Context + Token Preflight

Loads config, then verifies the Slack token and its scopes **before** any collection.
A missing scope must abort the run with an actionable error — never "complete with 0 files".

```bash
source ~/.claude/skills/_pm-shared/context.sh
echo "Sources: $HUDDLE_SOURCE_CHANNELS | Vault: $HUDDLE_VAULT_REPO/$HUDDLE_VAULT_PATH"

# ── Preflight: token valid? ──────────────────────────────────────────
AUTH=$(curl -s -D /tmp/huddle-auth-headers.txt "https://slack.com/api/auth.test" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN")
if [ "$(echo "$AUTH" | jq -r '.ok')" != "true" ]; then
  echo "FATAL: auth.test failed → $(echo "$AUTH" | jq -r '.error // "no response"')"
  echo "  Fix: set SLACK_BOT_TOKEN to a valid bot token (xoxb-...)."
  exit 1
fi
echo "Bot: $(echo "$AUTH" | jq -r '.user') @ $(echo "$AUTH" | jq -r '.team')"

# ── Preflight: required scopes present? ──────────────────────────────
# channels:read / groups:read       → resolve public/private channel IDs
# channels:history / groups:history → huddle-thread scan + fallback canvas scan
# files:read                        → enumerate + download huddle canvases
# users:read                        → resolve user IDs to names in transcripts
REQUIRED_SCOPES="channels:read groups:read channels:history groups:history files:read users:read"
GRANTED=$(grep -i '^x-oauth-scopes:' /tmp/huddle-auth-headers.txt \
  | cut -d' ' -f2- | tr -d '\r' | tr ',' '\n' | sed 's/^ *//')

MISSING=""
for s in $REQUIRED_SCOPES; do
  echo "$GRANTED" | grep -qx "$s" || MISSING="$MISSING $s"
done

if [ -n "$MISSING" ]; then
  echo "FATAL: bot token is missing required scopes:$MISSING"
  echo "  Fix: api.slack.com/apps → your app → OAuth & Permissions → Bot Token Scopes,"
  echo "  add the missing scopes, then REINSTALL the app to the workspace"
  echo "  (scope changes only take effect after reinstall)."
  exit 1
fi
echo "Scope preflight OK"
```
