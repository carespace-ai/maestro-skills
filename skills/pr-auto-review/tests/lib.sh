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

# reviews <state>... — write a bot review list (oldest first) and print its path
reviews() {
  local f; f="$(mktemp)"
  python3 - "$f" "$@" <<'PY'
import json, sys
out, states = sys.argv[1], sys.argv[2:]
json.dump([{"id": i, "state": s, "user": {"login": "maestro-bot"}, "body": f"review {i}"}
           for i, s in enumerate(states)], open(out, "w"))
PY
  echo "$f"
}

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }
