# Stack checklist — Python / FastAPI

Blocker candidates only. Each still has to pass the three-part test in SKILL.md
STEP 3 (breaks something · exact line + scenario · confident).

- Route missing the auth dependency its siblings use.
- Alembic migration that is destructive or non-reversible on live data without a backfill.
- Blocking/long work moved into the API process where the Context Layer says it must run in the worker.
- SQL built with f-strings from request input.
- Sync I/O inside `async def` on a hot path that would stall the event loop (only if it clearly would).
