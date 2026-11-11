#!/usr/bin/env bash
# Shared test helpers for pr-auto-review.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$HERE/../scripts"
FIX="$HERE/fixtures"
export PRR_HOME="$(mktemp -d)"   # never pick up a real ~/.prr token in tests

# mutate <fixture> <python-expr-on-p> — print the fixture JSON after applying an edit to `p`
mutate() {
  python3 - "$FIX/$1" "$2" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
exec(sys.argv[2])
print(json.dumps(p))
PY
}

# reviews <state[:verdict]>... — write a bot review list (oldest first) and print its
# path. With :verdict the body carries the marker post-review.sh writes.
reviews() {
  local f; f="$(mktemp)"
  python3 - "$f" "$@" <<'PY'
import json, sys
out, states = sys.argv[1], sys.argv[2:]
def review(i, spec):
    state, _, verdict = spec.partition(":")
    body = f"review {i}" + (f"\n\n<!-- maestro-pr-review sha=old{i} verdict={verdict} -->" if verdict else "")
    return {"id": i, "state": state, "user": {"login": "maestro-bot"}, "body": body}
json.dump([review(i, s) for i, s in enumerate(states)], open(out, "w"))
PY
  echo "$f"
}

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }
