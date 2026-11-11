#!/usr/bin/env bash
# Repo profiles: the registry is well-formed and each PR gets the profile it needs.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
T="$(mktemp -d)"
kv() { echo "$1" | sed -n "s/^$2=//p"; }
resolve() { printf '%s\n' "${@:2}" > "$T/files.txt"; python3 "$SCRIPTS/resolve-profile.py" "$1" "$T/files.txt" "$T"; }

OUT="$(python3 "$SCRIPTS/validate-registry.py")" || fail "registry has errors: $OUT"; pass "every repo profile validates"

OUT="$(resolve carespace-ai/carespace-agent src/carespace_agent/cards.py src/carespace_agent/tools/patient.py)"
[ "$(kv "$OUT" PROFILE)" = carespace-agent ] || fail "profile name (got: $OUT)"; pass "profile resolved from owner/repo"
[ "$(kv "$OUT" STACKS)" = python ] || fail "only the touched stack (got: $OUT)"; pass "only the touched stack is loaded"
[ "$(kv "$OUT" RISK_FILES)" = 1 ] || fail "one risk file (got: $OUT)"; pass "risk file detected"
grep -q "^src/carespace_agent/cards.py	" "$T/risk-files.txt" || fail "risk-files.txt"; pass "risk-files.txt lists it with its reason"
grep -q "## What breaks here" "$T/profile.md" || fail "repo notes missing"; pass "repo notes staged"
grep -q "Stack checklist — Python" "$T/profile.md" || fail "stack checklist missing"; pass "stack checklist staged"
grep -q "Stack checklist — Infra" "$T/profile.md" && fail "untouched stack must not load"; pass "untouched stack not loaded"

OUT="$(resolve carespace-mobile lib/features/home/home_screen.dart .github/workflows/ci.yml docs/adr/0001.md)"
[ "$(kv "$OUT" STACKS)" = flutter,infra ] || fail "two stacks (got: $OUT)"; pass "multi-stack PR loads both checklists"
[ "$(kv "$OUT" RISK_FILES)" = 1 ] || fail "workflow is a risk file (got: $OUT)"; pass "feature file is not a risk file"

OUT="$(resolve carespace-mobile docs/adr/0001.md)"
[ -z "$(kv "$OUT" STACKS)" ] && [ "$(kv "$OUT" RISK_FILES)" = 0 ] || fail "docs-only PR (got: $OUT)"; pass "docs-only PR loads no checklist"

OUT="$(resolve some-new-repo src/users/users.controller.ts prisma/migrations/1/migration.sql web/App.tsx)"
[ "$(kv "$OUT" PROFILE)" = default ] || fail "unknown repo → default (got: $OUT)"; pass "repo without a profile falls back"
[ "$(kv "$OUT" STACKS)" = nestjs-prisma,react ] || fail "default stack detection (got: $OUT)"; pass "default profile guesses the stacks"
[ "$(kv "$OUT" RISK_FILES)" = 1 ] || fail "default risk paths (got: $OUT)"; pass "default profile flags the migration"
grep -q "no review profile yet" "$T/profile.md" || fail "default notice"; pass "default profile says it is generic"

# glob semantics the profiles rely on
python3 - "$SCRIPTS" <<'PY' || fail "glob semantics"
import sys
sys.path.insert(0, sys.argv[1])
from _profiles import matches
assert matches("lib/a/b.dart", ["lib/**"])
assert matches("packages/scan/lib/scan.dart", ["packages/*/lib/*.dart"])
assert not matches("packages/scan/lib/src/x.dart", ["packages/*/lib/*.dart"])
assert matches("a/b/migrations/1/x.sql", ["**/migrations/**"])
assert matches("Dockerfile.prod", ["Dockerfile*"]) and not matches("docker/Dockerfile", ["Dockerfile*"])
assert not matches("pubspec.yaml.bak", ["pubspec.yaml"])
PY
pass "glob semantics"

# ci_ignore from the profile reaches the approve gate through status.env
B="$(mktemp -d)"; echo "ok" > "$B/review.md"; printf 'DIFF_STATUS=ok\nHUMAN_FILES=0\nCI_IGNORE=^preview\n' > "$B/status.env"
echo '{"check_runs":[{"name":"preview deploy","status":"completed","conclusion":"failure"}]}' > "$B/ci.json"
P="$(PRR_RAW_BODY=1 PRR_CI_WAIT=0 PRR_CI_FILE="$B/ci.json" PRR_DRY_RUN=1 bash "$SCRIPTS/post-review.sh" o/r 1 abc APPROVE "$B/review.md")"
echo "$P" | grep -q '"event": "APPROVE"' || fail "profile ci_ignore should keep the approve (got: $P)"; pass "profile ci_ignore reaches the approve gate"

# human_paths — files the bot never approves on its own
OUT="$(resolve carespace-mobile lib/features/home/home_page.dart .github/workflows/ci.yml)"
[ "$(kv "$OUT" HUMAN_FILES)" = 1 ] && [ "$(cat "$T/human-files.txt")" = .github/workflows/ci.yml ] || fail "workflow change is human-only (got: $OUT)"; pass "human_paths: workflow change listed"
OUT="$(resolve carespace-mobile lib/features/home/home_page.dart)"
[ "$(kv "$OUT" HUMAN_FILES)" = 0 ] && [ ! -s "$T/human-files.txt" ] || fail "ordinary change is not human-only (got: $OUT)"; pass "human_paths: ordinary change not held"
OUT="$(resolve some-unprofiled-repo .github/workflows/deploy.yml src/a.ts)"
[ "$(kv "$OUT" HUMAN_FILES)" = 1 ] || fail "unprofiled repo gets the default human paths (got: $OUT)"; pass "human_paths: default applies without a profile"
echo "ALL PASS"
