#!/usr/bin/env bash
# Onboarding: a generated profile is valid, and an unfinished one cannot pass validation.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"
kv() { echo "$1" | sed -n "s/^$2=//p"; }
NAME="zz-onboard-test-$$"; OUT="$SCRIPTS/../repos/$NAME"
trap 'rm -rf "$OUT"' EXIT

printf '%s\n' AGENTS.md src/AGENTS.md src/users/users.controller.ts src/users/users.service.ts \
  src/auth/auth.guard.ts prisma/schema.prisma prisma/migrations/1/migration.sql web/App.tsx \
  .github/workflows/ci.yml Dockerfile node_modules/x/index.tsx README.md > "$T/tree.txt"
cat > "$T/AGENTS.md" <<'MD'
# api
## What this repo is
Backend. Consumed by carespace-mobile and carespace-ui.
## Hard rules
1. HARD-RULE-ONE no PHI in logs.
## Layout
src/
## App Integration
| carespace-mobile | this | REST |
MD

OUT_KV="$(python3 "$SCRIPTS/onboard-scan.py" "acme/$NAME" main "$T/tree.txt" "$T/AGENTS.md" "$OUT")" || fail "scan failed"
[ "$(kv "$OUT_KV" ONBOARD_STACKS)" = nestjs-prisma,react,infra ] || fail "stacks (got: $OUT_KV)"; pass "stacks detected from the tree"
[ "$(kv "$OUT_KV" ONBOARD_CONTEXT_NODES)" = 2 ] || fail "context nodes (got: $OUT_KV)"; pass "Context Layer nodes counted"
[ "$(kv "$OUT_KV" ONBOARD_RELATED)" = carespace-mobile,carespace-ui ] || fail "related repos (got: $OUT_KV)"; pass "related repos found in AGENTS.md"
python3 - "$OUT/profile.json" "$NAME" <<'PY' || fail "generated profile content"
import json, sys
p = json.load(open(sys.argv[1]))
assert p["repo"] == sys.argv[2] and p["default_branch"] == "main"
assert p["stacks"]["nestjs-prisma"] == ["prisma/**", "src/**"], p["stacks"]
assert p["stacks"]["react"] == ["web/**"], p["stacks"]            # node_modules ignored
assert "Dockerfile" in p["stacks"]["infra"] and ".github/**" in p["stacks"]["infra"], p["stacks"]
globs = [r["glob"] for r in p["risk_paths"]]
assert "**/migrations/**" in globs and "**/*auth*" in globs and "**/*.bicep" not in globs, globs
PY
pass "generated profile.json is specific to the tree"
grep -q "HARD-RULE-ONE" "$OUT/ONBOARDING.md" && grep -q "carespace-mobile | this" "$OUT/ONBOARDING.md" || fail "source material"; pass "ONBOARDING.md quotes the repo's rules"
grep -q "src/$" "$OUT/ONBOARDING.md" && fail "non-priority sections must not be quoted"; pass "only rule / integration sections are quoted"

V="$(python3 "$SCRIPTS/validate-registry.py")" && fail "an unfinished onboarding must fail validation"
echo "$V" | grep -q "$NAME: review.md still has {{placeholders}}" || fail "placeholder error (got: $V)"; pass "placeholders block validation"
echo "$V" | grep -q "$NAME: ONBOARDING.md is still there" || fail "ONBOARDING.md error (got: $V)"; pass "leftover ONBOARDING.md blocks validation"

printf '## What breaks here\n\n- x\n\n## Not a blocker here\n\n- y\n' > "$OUT/review.md"; rm "$OUT/ONBOARDING.md"
python3 "$SCRIPTS/validate-registry.py" > /dev/null || fail "a finished onboarding must validate"; pass "finished onboarding validates"

OUT_KV="$(python3 "$SCRIPTS/onboard-scan.py" "$NAME" main <(echo README.md) - "$T/empty")"
[ -z "$(kv "$OUT_KV" ONBOARD_STACKS)" ] && [ "$(kv "$OUT_KV" ONBOARD_CONTEXT_NODES)" = 0 ] || fail "bare repo (got: $OUT_KV)"
grep -q "No Context Layer" "$T/empty/ONBOARDING.md" && grep -q "none was detected" "$T/empty/ONBOARDING.md" || fail "bare repo warnings"
pass "repo with no stack and no Context Layer is called out"
echo "ALL PASS"
