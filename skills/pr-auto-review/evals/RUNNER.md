# Running one eval case

You are reviewing a **historic, already merged PR** to measure the reviewer. Nothing
is posted: the run env sets `PRR_DRY_RUN=1`, so `post-review.sh` prints the review
payload instead of calling GitHub.

1. `scripts/eval-stage.sh <case-id>` printed `RUN_ENV=` and `PRR_DIR=`. The context
   is already staged in `PRR_DIR` — do **not** run STEP 0 or `fetch-context.sh`.
2. Follow `SKILL.md` from "Files land in `$PRR_DIR`. Read, in this order" through
   STEP 4, exactly as a `full` review, with `source "<RUN_ENV>"` at the top of every
   Bash block.
3. In STEP 4, save what `post-review.sh` prints:

   ```bash
   source "<RUN_ENV>"
   bash "$S/post-review.sh" "$REPO_FULL" "$PR_NUMBER" "$HEAD_SHA" <VERDICT> \
     "$PRR_DIR/review.json" > "$PRR_DIR/payload.json"
   ```
4. Skip STEP 5. Stop.

Rules that keep the measurement honest:

- Use only what is staged in `PRR_DIR` and what `SKILL.md` lets a reviewer open (the
  repo at the PR's commits, the consumer copies under `cross/`).
- Do **not** open `evals/cases.json`, and do not look at later PRs, issues, commits
  or the repo's current default branch: the answer is there.
