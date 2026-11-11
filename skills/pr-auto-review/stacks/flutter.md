# Stack checklist — Flutter / Dart

Blocker candidates only. Each still has to pass the three-part test in SKILL.md
STEP 3 (breaks something · exact line + scenario · confident).

- Null-check `!` on data that the API can return null → crash.
- `BuildContext` used after `await` without `mounted` check in a navigation/dialog path.
- Platform channel / permission change without the matching Android manifest / iOS Info.plist entry → crash or store rejection.
- Asset or path dependency referenced but not declared in `pubspec.yaml`.
- Breaking change to a model's `fromJson` that the backend still sends in the old shape.
