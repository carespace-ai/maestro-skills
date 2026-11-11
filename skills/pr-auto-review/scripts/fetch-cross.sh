#!/usr/bin/env bash
# fetch-cross.sh — stage the other side of each cross-repo contract a PR touches,
# so the reviewer can grep / read real consumer or provider code instead of
# trusting what a document says about it.
#
# Usage: fetch-cross.sh <OWNER> <PRR_DIR>
#
# Reads <PRR_DIR>/cross.tsv (written by resolve-relations.py):
#   <edge id> TAB <repo> TAB <glob>,<glob>…
# For each repo: one shallow, blob-less, sparse checkout of its DEFAULT branch
# into <PRR_DIR>/cross/<repo>/, limited to the union of the globs. Read-only —
# nothing is ever pushed. A repo the reviewer identity cannot read (App not
# installed there) is reported as unavailable; the review goes on without it.
#
# Prints CROSS_<repo>=ok|unavailable (+ CROSS_FILES_<repo>=<n>) and CROSS_STAGED=<n>.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_auth.sh"

OWNER="${1:?OWNER}"; DIR="${2:?PRR_DIR}"
TSV="$DIR/cross.tsv"
[ -s "$TSV" ] || { echo "CROSS_STAGED=0"; exit 0; }
TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
AUTH=()
[ -n "$TOKEN" ] && AUTH=(-c "http.https://github.com/.extraheader=Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')")
BASE_URL="${PRR_CROSS_BASE_URL:-https://github.com}"   # test seam: a local directory of bare repos
mkdir -p "$DIR/cross"; STAGED=0

for repo in $(cut -f2 "$TSV" | sort -u); do
  key="$(echo "$repo" | tr -c 'A-Za-z0-9\n' '_')"
  dest="$DIR/cross/$repo"; rm -rf "$dest"
  # union of this repo's globs, as non-cone sparse patterns anchored at the root
  patterns="$(awk -F'\t' -v r="$repo" '$2==r {print $3}' "$TSV" | tr ',' '\n' | sort -u | sed 's#^#/#')"
  if timeout "${PRR_CROSS_TIMEOUT:-90}" git -c credential.helper= "${AUTH[@]}" clone -q \
        --depth 1 --filter=blob:none --sparse --no-tags "$BASE_URL/$OWNER/$repo" "$dest" 2> "$DIR/cross/.$repo.err" \
     && git -C "$dest" sparse-checkout set --no-cone $patterns 2>> "$DIR/cross/.$repo.err" \
     && timeout "${PRR_CROSS_TIMEOUT:-90}" git -C "$dest" -c credential.helper= "${AUTH[@]}" checkout -q 2>> "$DIR/cross/.$repo.err"; then
    sha="$(git -C "$dest" rev-parse --short HEAD 2>/dev/null)"
    rm -rf "$dest/.git"            # a plain directory: nothing to push, no token left behind
    n="$(find "$dest" -type f | wc -l | tr -d ' ')"
    echo "CROSS_$key=ok"; echo "CROSS_FILES_$key=$n"; echo "CROSS_SHA_$key=$sha"
    STAGED=$((STAGED + 1))
  else
    rm -rf "$dest"
    echo "CROSS_$key=unavailable"
  fi
done
echo "CROSS_STAGED=$STAGED"
