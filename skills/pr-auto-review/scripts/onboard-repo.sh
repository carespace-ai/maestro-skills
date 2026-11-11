#!/usr/bin/env bash
# onboard-repo.sh — start the review profile of a new repo and report what is
# still missing before it can be enrolled.
#
# Usage: onboard-repo.sh <owner/repo> [--force]
#
# Read-only against GitHub. Locally it creates repos/<repo>/ with a generated
# profile.json, the review.md template and ONBOARDING.md (the to-do list plus
# the repo's own rules as source material). It never touches the repo, its
# webhooks, the GitHub App or the Maestro trigger — it only tells you their state.
#
# Readiness lines are READY_<check>=yes|no|unknown ("unknown" = the token in use
# may not see it, e.g. webhooks need admin). Refuses to overwrite an existing
# profile unless --force.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_auth.sh"

FULL="${1:?owner/repo}"; FORCE="${2:-}"
case "$FULL" in */*) ;; *) echo "ERROR=pass owner/repo"; exit 2 ;; esac
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${FULL##*/}"; OUT="$HERE/../repos/$REPO"
[ -e "$OUT/profile.json" ] && [ "$FORCE" != "--force" ] && { echo "ERROR=repos/$REPO already has a profile (use --force to regenerate)"; exit 2; }
TMP="$(mktemp -d)"

BRANCH="$(gh api "repos/$FULL" --jq .default_branch 2>/dev/null)" || { echo "ERROR=cannot read $FULL (does the reviewer identity have access?)"; exit 1; }
gh api "repos/$FULL/git/trees/$BRANCH?recursive=1" --jq '.tree[] | select(.type=="blob") | .path' > "$TMP/tree.txt" 2>/dev/null \
  || { echo "ERROR=cannot read the file tree of $FULL@$BRANCH"; exit 1; }
gh api "repos/$FULL/contents/AGENTS.md?ref=$BRANCH" -H 'Accept: application/vnd.github.raw' > "$TMP/AGENTS.md" 2>/dev/null || rm -f "$TMP/AGENTS.md"

python3 "$HERE/onboard-scan.py" "$REPO" "$BRANCH" "$TMP/tree.txt" "$([ -s "$TMP/AGENTS.md" ] && echo "$TMP/AGENTS.md" || echo -)" "$OUT" \
  || { echo "ERROR=profile generation failed"; exit 1; }
echo "ONBOARD_DIR=$(cd "$OUT" && pwd)"
echo "ONBOARD_BRANCH=$BRANCH"

# ── Readiness (read-only) ────────────────────────────────────────────────────
yn() { [ "$1" -gt 0 ] 2>/dev/null && echo yes || echo no; }
echo "READY_context_layer=$(yn "$(grep -c '\(^\|/\)AGENTS.md$' "$TMP/tree.txt")")"
echo "READY_ci_workflows=$(yn "$(grep -c '^\.github/workflows/' "$TMP/tree.txt")")"

if HOOKS="$(gh api "repos/$FULL/hooks" --jq '[.[] | select(.active and (.events | index("pull_request")) and (.events | index("issue_comment")))] | length' 2>/dev/null)"; then
  echo "READY_webhook_pull_request_and_comment=$(yn "$HOOKS")"
else
  echo "READY_webhook_pull_request_and_comment=unknown"
fi

if gh api "repos/$FULL/rules/branches/$BRANCH" > "$TMP/rules.json" 2>/dev/null; then
  python3 - "$TMP/rules.json" <<'PY'
import json, sys
rules = json.load(open(sys.argv[1]))
pr = [r for r in rules if r.get("type") == "pull_request"]
approvals = max([(r.get("parameters") or {}).get("required_approving_review_count", 0) for r in pr] or [0])
code_owner = any((r.get("parameters") or {}).get("require_code_owner_review") for r in pr)
checks = [c.get("context") for r in rules if r.get("type") == "required_status_checks"
          for c in (r.get("parameters") or {}).get("required_status_checks", [])]
yn = lambda v: "yes" if v else "no"
print(f"READY_ruleset_requires_approval={yn(approvals)}")
print(f"READY_ruleset_required_checks={yn(checks)}")
print("ONBOARD_REQUIRED_CHECKS=" + ", ".join(checks))
print(f"ONBOARD_CODE_OWNER_REVIEW={yn(code_owner)}")
PY
else
  echo "READY_ruleset_requires_approval=unknown"; echo "READY_ruleset_required_checks=unknown"
fi

if gh api "repos/$FULL/labels/maestro:override" > /dev/null 2>&1; then echo "READY_override_label=yes"; else echo "READY_override_label=no"; fi
echo "READY_in_relations=$(yn "$(grep -c "\"$REPO\"" "$HERE/../relations.json")")"

cat <<EOT

NEXT
  1. Work through repos/$REPO/ONBOARDING.md, then delete it.
  2. python3 scripts/validate-registry.py   → REGISTRY_ERRORS=0
  3. Outside this repo (not done by this script):
       - GitHub App carespace-maestro-review installed on $FULL
       - webhook (pull_request + issue_comment) orchestrated in Maestro
       - "$REPO" added to the trigger's prr_repos
     READY_ruleset_required_checks=no means the bot's approve is the only gate on merge:
     with CODE_OWNER_REVIEW=yes a human approve is still required (apps cannot be code owners).
EOT
