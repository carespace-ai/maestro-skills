#!/usr/bin/env python3
"""Print one sha256 over every script in this directory.

should-run.sh records it in the run env as SCRIPTS_SHA; post-review.sh recomputes
it and posts nothing when it differs — a run that patched a failing script to get
past it must not publish a review.
"""
import hashlib
import os
import sys

here = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
digest = hashlib.sha256()
for name in sorted(os.listdir(here)):
    if name.endswith((".sh", ".py")):
        digest.update(name.encode() + b"\0")
        with open(os.path.join(here, name), "rb") as fh:
            digest.update(fh.read() + b"\0")
print(digest.hexdigest())
