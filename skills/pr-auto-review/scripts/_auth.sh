# _auth.sh — sourced by every script. If app-token.sh minted a GitHub App
# installation token, act as the App: GH_TOKEN wins over GITHUB_TOKEN in gh,
# and PRR_BOT_LOGIN tells should-run.sh who the reviewer is (App tokens can't
# call GET /user). Otherwise leave the PAT ($GITHUB_TOKEN) in charge.
_prr_home="${PRR_HOME:-$HOME/.prr}"
if [ -s "$_prr_home/token" ]; then
  export GH_TOKEN="$(cat "$_prr_home/token")"
  [ -s "$_prr_home/login" ] && export PRR_BOT_LOGIN="${PRR_BOT_LOGIN:-$(cat "$_prr_home/login")}"
fi
unset _prr_home
