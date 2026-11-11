# Stack checklist — Infra / CI / config

Blocker candidates only. Each still has to pass the three-part test in SKILL.md
STEP 3 (breaks something · exact line + scenario · confident).

- Workflow/CI change that disables required checks or exposes secrets to PRs from forks.
- Dockerfile/compose change that removes a needed env, port or volume.
- Committed credentials, private keys, `.env` files.
