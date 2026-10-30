#!/usr/bin/env bash
# GitHub App auth: no secrets → PAT, JWT is a valid RS256 signature for every
# key format Maestro may store, and _auth.sh hands the App token to gh/scripts.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"
openssl genrsa -out "$T/k.pem" 2048 2>/dev/null
openssl rsa -in "$T/k.pem" -pubout -out "$T/pub.pem" 2>/dev/null

OUT="$(PRR_APP_ID= PRR_APP_PRIVATE_KEY= bash "$SCRIPTS/app-token.sh")"
[ "$OUT" = TOKEN_SOURCE=pat ] || fail "no secrets should fall back to PAT ($OUT)"; pass "no App secrets → PAT"

verify() {  # verify <jwt> — RS256 signature + iss claim
  local jwt="$1" h p s
  IFS=. read -r h p s <<< "$jwt"
  printf '%s' "$s" | tr '_-' '/+' | awk '{l=length($0)%4; if(l) $0=$0 substr("==",1,4-l); print}' | openssl base64 -d -A > "$T/sig"
  printf '%s.%s' "$h" "$p" | openssl dgst -sha256 -verify "$T/pub.pem" -signature "$T/sig" >/dev/null || return 1
  printf '%s' "$p" | tr '_-' '/+' | awk '{l=length($0)%4; if(l) $0=$0 substr("==",1,4-l); print}' | openssl base64 -d -A | grep -q '"iss":"4242"'
}
PEM="$(cat "$T/k.pem")"
J="$(PRR_APP_JWT_ONLY=1 PRR_APP_ID=4242 PRR_APP_PRIVATE_KEY="$PEM" bash "$SCRIPTS/app-token.sh")"
verify "$J" || fail "PEM key JWT"; pass "PEM key → valid JWT"
ESC="$(awk '{printf "%s\\n", $0}' "$T/k.pem")"
J="$(PRR_APP_JWT_ONLY=1 PRR_APP_ID=4242 PRR_APP_PRIVATE_KEY="$ESC" bash "$SCRIPTS/app-token.sh")"
verify "$J" || fail "escaped-newline key JWT"; pass "single-line \\n key → valid JWT"
B64="$(base64 -w0 "$T/k.pem")"
J="$(PRR_APP_JWT_ONLY=1 PRR_APP_ID=4242 PRR_APP_PRIVATE_KEY="$B64" bash "$SCRIPTS/app-token.sh")"
verify "$J" || fail "base64 key JWT"; pass "base64 key → valid JWT"
OUT="$(PRR_APP_ID=4242 PRR_APP_PRIVATE_KEY=garbage bash "$SCRIPTS/app-token.sh")"
echo "$OUT" | grep -q TOKEN_SOURCE=pat || fail "bad key should fall back"; pass "bad key → PAT + warning"

printf 'ghs_test' > "$PRR_HOME/token"; printf 'maestro-reviewer[bot]' > "$PRR_HOME/login"
R="$(GITHUB_TOKEN=pat_x PRR_BOT_LOGIN= bash -c 'unset PRR_BOT_LOGIN; source "$1/_auth.sh"; echo "$GH_TOKEN $PRR_BOT_LOGIN"' _ "$SCRIPTS")"
[ "$R" = "ghs_test maestro-reviewer[bot]" ] || fail "_auth.sh ($R)"; pass "_auth.sh exports App token + bot login"
echo "ALL PASS"
