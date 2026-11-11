#!/usr/bin/env bash
# Cross-repo relations: the right contracts trigger, on the right side, and the
# other repo is staged (or honestly reported as unavailable).
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"
kv() { echo "$1" | sed -n "s/^$2=//p"; }
rel() { printf '%s\n' "${@:2}" > "$T/files.txt"; python3 "$SCRIPTS/resolve-relations.py" "$1" "$T/files.txt" "$T"; }

OUT="$(python3 "$SCRIPTS/validate-registry.py")" || fail "registry has errors: $OUT"; pass "relations.json validates"

OUT="$(rel carespace-ai/carespace-agent src/carespace_agent/cards.py)"
[ "$(kv "$OUT" RELATION_IDS)" = agent-protocol:provider ] || fail "agent card change (got: $OUT)"; pass "provider-side edge triggers"
grep -q "immediate coupling" "$T/relations.md" && grep -q "is a \*\*blocker\*\*" "$T/relations.md" || fail "immediate provider rule"; pass "immediate coupling → blocker rule"
grep -q "^agent-protocol	carespace-mobile	.*lib/features/assistant/\*\*" "$T/cross.tsv" || fail "cross.tsv consumer paths"; pass "consumer paths queued for staging"

OUT="$(rel carespace-agent src/carespace_agent/analysis/trend.py tests/test_trend.py)"
[ "$(kv "$OUT" RELATIONS)" = 0 ] && [ ! -s "$T/relations.md" ] && [ ! -s "$T/cross.tsv" ] || fail "internal change (got: $OUT)"; pass "internal change triggers nothing"

OUT="$(rel carespace-sdk packages/scan/lib/src/pose_camera_view.dart)"
[ "$(kv "$OUT" RELATION_IDS)" = sdk-packages:provider ] || fail "sdk public api (got: $OUT)"; pass "sdk provider edge triggers"
grep -q "never a blocker" "$T/relations.md" || fail "deferred provider rule"; pass "deferred coupling → heads-up rule"

OUT="$(rel carespace-mobile lib/data/api/agent_api.dart)"
echo "$(kv "$OUT" RELATION_IDS)" | tr ',' '\n' | grep -qx "agent-protocol:consumer" || fail "mobile consumes agent (got: $OUT)"; pass "consumer-side edge triggers"
echo "$(kv "$OUT" RELATION_IDS)" | tr ',' '\n' | grep -qx "admin-rest-mobile:consumer" || fail "mobile consumes admin (got: $OUT)"; pass "one file can sit on two contracts"
grep -q "^admin-rest-mobile	carespace-admin	openapi.json$" "$T/cross.tsv" || fail "provider_stage"; pass "provider_stage narrows what is staged"

OUT="$(rel some-other-repo src/x.ts)"
[ "$(kv "$OUT" RELATIONS)" = 0 ] || fail "unknown repo (got: $OUT)"; pass "repo with no edges"

# fetch-cross.sh against local bare repos (no network)
SRV="$T/srv/acme"; mkdir -p "$SRV" "$T/work"
( cd "$T/work" && git init -q -b main consumer && cd consumer \
  && mkdir -p lib/features/assistant lib/other && echo "final kind = json['kind'];" > lib/features/assistant/card.dart \
  && echo x > lib/other/skip.dart && echo y > README.md \
  && git -c user.email=t@t -c user.name=t add -A && git -c user.email=t@t -c user.name=t commit -qm init \
  && git clone -q --bare . "$SRV/consumer" && git -C "$SRV/consumer" config uploadpack.allowFilter true \
  && git -C "$SRV/consumer" config uploadpack.allowAnySHA1InWant true ) || fail "could not build the fixture repo"
D="$T/prr"; mkdir -p "$D"
printf 'e1\tconsumer\tlib/features/assistant/**\ne2\tmissing-repo\tsrc/**\n' > "$D/cross.tsv"
OUT="$(PRR_CROSS_BASE_URL="file://$T/srv" GH_TOKEN= GITHUB_TOKEN= bash "$SCRIPTS/fetch-cross.sh" acme "$D")"
[ "$(kv "$OUT" CROSS_consumer)" = ok ] || fail "consumer should be staged (got: $OUT)"; pass "other repo staged"
[ -f "$D/cross/consumer/lib/features/assistant/card.dart" ] || fail "staged file missing"; pass "contract files present"
[ ! -e "$D/cross/consumer/lib/other/skip.dart" ] || fail "sparse checkout should leave other paths out"; pass "only the contract paths are checked out"
[ ! -e "$D/cross/consumer/.git" ] || fail ".git must be removed"; pass "staged copy is a plain directory"
[ "$(kv "$OUT" CROSS_missing_repo)" = unavailable ] || fail "unreadable repo → unavailable (got: $OUT)"; pass "unreadable repo reported, not fatal"
[ "$(kv "$OUT" CROSS_STAGED)" = 1 ] || fail "CROSS_STAGED (got: $OUT)"; pass "CROSS_STAGED counts"
: > "$D/cross.tsv"
[ "$(bash "$SCRIPTS/fetch-cross.sh" acme "$D")" = "CROSS_STAGED=0" ] || fail "empty cross.tsv"; pass "nothing to stage"
echo "ALL PASS"
