#!/usr/bin/env bash
# app-token.sh — when the reviewer is a GitHub App, mint a short-lived
# installation token for the webhook's repo and save it for the other scripts.
#
# Uses Maestro saved secrets (injected as env):
#   PRR_APP_ID            numeric App ID
#   PRR_APP_PRIVATE_KEY   the App's private key — PEM, PEM with literal "\n",
#                         or the whole .pem base64-encoded on one line
# Without them it does nothing and the skill keeps using $GITHUB_TOKEN (PAT).
#
# Writes $PRR_HOME/token and $PRR_HOME/login (default ~/.prr); _auth.sh loads them
# so every script (and gh) acts as "<app-slug>[bot]" instead of the PAT owner.
# Prints TOKEN_SOURCE=app|pat (+ BOT_LOGIN for app). Exit code is always 0 —
# should-run.sh SKIPs when no GitHub identity can be resolved.
#
# Test seams: PRR_APP_JWT_ONLY=1 prints the JWT and stops (no network).
set -uo pipefail

PRR_HOME="${PRR_HOME:-$HOME/.prr}"
rm -f "$PRR_HOME/token" "$PRR_HOME/login"
if [ -z "${PRR_APP_ID:-}" ] || [ -z "${PRR_APP_PRIVATE_KEY:-}" ]; then
  echo "TOKEN_SOURCE=pat"; exit 0
fi
mkdir -p "$PRR_HOME" && chmod 700 "$PRR_HOME"
KEY="$(mktemp)"; trap 'rm -f "$KEY"' EXIT; chmod 600 "$KEY"

case "$PRR_APP_PRIVATE_KEY" in
  *BEGIN*) printf '%b\n' "$PRR_APP_PRIVATE_KEY" > "$KEY" ;;
  *)       printf '%s' "$PRR_APP_PRIVATE_KEY" | base64 -d > "$KEY" 2>/dev/null ;;
esac
grep -q "PRIVATE KEY" "$KEY" || { echo "TOKEN_SOURCE=pat"; echo "WARN=PRR_APP_PRIVATE_KEY is not a PEM key"; exit 0; }

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
NOW="$(date +%s)"
HEADER="$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)"
PAYLOAD="$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((NOW - 60)) $((NOW + 540)) "$PRR_APP_ID" | b64url)"
SIG="$(printf '%s.%s' "$HEADER" "$PAYLOAD" | openssl dgst -sha256 -sign "$KEY" | b64url)"
JWT="$HEADER.$PAYLOAD.$SIG"
[ "${PRR_APP_JWT_ONLY:-}" = 1 ] && { echo "$JWT"; exit 0; }

JWT="$JWT" PRR_HOME="$PRR_HOME" python3 - <<'PY'
import json, os, sys, urllib.request

def api(path, method="GET"):
    req = urllib.request.Request(
        f"https://api.github.com/{path}", method=method,
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": f"Bearer {os.environ['JWT']}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

try:
    p = json.loads(os.environ.get("CLAUDEHUB_INPUT_KWARGS") or "{}")
except ValueError:
    p = {}
repo = (p.get("repository") or {}).get("full_name") or ""
try:
    slug = api("app")["slug"]
    inst = api(f"repos/{repo}/installation") if repo else api("orgs/carespace-ai/installation")
    tok = api(f"app/installations/{inst['id']}/access_tokens", method="POST")["token"]
except Exception as e:
    print("TOKEN_SOURCE=pat")
    print(f"WARN=GitHub App token failed ({e}) — App not installed on {repo or 'org'}?")
    sys.exit(0)

home = os.environ["PRR_HOME"]
login = f"{slug}[bot]"
for name, val in (("token", tok), ("login", login)):
    path = os.path.join(home, name)
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        f.write(val)
print("TOKEN_SOURCE=app")
print(f"BOT_LOGIN={login}")
PY
