# Stack checklist — NestJS / Prisma

Blocker candidates only. Each still has to pass the three-part test in SKILL.md
STEP 3 (breaks something · exact line + scenario · confident).

- New/changed controller route without the guard its siblings use (`@UseGuards`, role/tenant checks) → unauthenticated or cross-tenant access.
- Prisma query that drops the tenant/clinic/patient scoping filter its siblings apply.
- `prisma migrate` that drops/renames a column or table still read by code in this repo or a documented consumer; `NOT NULL` added without default/backfill.
- DTO/response shape change on an endpoint the Context Layer lists as consumed by another app (mobile, web, bots).
- PHI (patient names, DOB, notes, media URLs) written to logs, error messages, analytics or 3rd-party calls.
- `await` missing on a write whose result is relied on; unhandled promise in a request path.
- New required env var read without default and not added to deploy config.
