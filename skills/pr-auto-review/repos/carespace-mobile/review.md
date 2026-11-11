Flutter app for patients, clinicians and the kiosk (one codebase). Talks to
carespace-admin over REST, embeds carespace-sdk packages pinned by tag, and
builds against carespace-widgetbook as a path dependency.

## What breaks here

- **PHI in a log line** (AGENTS.md hard rule 1) — a new `print` / `debugPrint` /
  logger call that interpolates ids, names, tokens, images or landmarks, or a
  `LogInterceptor` that survives into release.
- **A token outside `flutter_secure_storage`** (hard rule 4), or a secret / `.env.*`
  file committed (hard rule 2).
- **Plain `http://`** anywhere except the QA-build proxy exception in `lib/core/qa.dart`
  (hard rule 3) — and that exception reachable from a store build.
- **`fromJson` out of step with the backend** — a model under `lib/data/api/` that
  now requires, renames or re-types a field carespace-admin still sends in the old
  shape crashes every screen that loads it.
- **A `carespace_sdk` / `carespace_scan` `ref:` in `pubspec.yaml` that is not a
  published tag** — the build cannot resolve it. Pins are moved by `sdk-bump.yml`.
- **A new permission or URL scheme used in Dart without its
  `AndroidManifest.xml` / `Info.plist` entry** — runtime crash or store rejection.
- **A route without its typed args, or a deep link whose target moved** — the
  scheduled-activity → deep-link flow lands on an error page.

## Not a blocker here

- Formatting, analyzer lints, tests and the coverage ratchet — the required check
  `Format · Analyze · Test` enforces them.
- Widgets, naming, state-class shape, route-table placement and the other "soft
  conventions" in AGENTS.md.
- Generated code (`*.g.dart`, `lib/l10n` output), `docs/**`, ADRs and `AGENTS.md` edits.
- A PR that needs an unmerged carespace-widgetbook change: CI builds against
  widgetbook's default branch and fails on its own.
