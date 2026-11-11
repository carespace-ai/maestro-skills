# Stack checklist — React / Next.js

Blocker candidates only. Each still has to pass the three-part test in SKILL.md
STEP 3 (breaks something · exact line + scenario · confident).

- Runtime crash on render: accessing a property of possibly-undefined API data with no guard on a path users hit.
- Hook rule violation (conditional hook) — crashes at runtime.
- API client call shape out of sync with the backend contract changed in the same PR group.
- Secrets/keys in client bundles (`NEXT_PUBLIC_*` holding a server secret).
- `dangerouslySetInnerHTML` with user/patient content.
