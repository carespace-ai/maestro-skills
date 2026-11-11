Flutter packages shipped to host apps: `packages/flutter` (main SDK),
`packages/scan` (on-device pose capture, native engines), `packages/scan_queue`
(offline queue) and the legacy ROM SDK in `lib/`. carespace-mobile consumes
`packages/flutter` and `packages/scan` pinned to release tags.

## What breaks here

- **A method channel whose Dart and native sides disagree** — channel name, method
  name or argument / result shape changed on one side only (`ai.carespace/pose_engine`,
  `ai.carespace/pose_camera`, `ai.carespace.rom_sdk/config`, `carespace_sdk/audio`).
  It compiles and fails at runtime on the device.
- **PHI escaping the device or the logs** — `SdkLogger` redaction weakened or
  bypassed, a `LogInterceptor` added to a Dio client, raw video / frames uploaded
  instead of derived measurements.
- **The `https://` assertion on a `baseUrl` removed or made conditional.**
- **`scan_queue` no longer failing closed** — draining or mutating rows without a
  `tokenProvider` token, the SQLCipher key logged, weakened or stored outside
  `flutter_secure_storage`, or a schema change with no migration for rows already
  on devices.
- **A release / tagging workflow change that stops a tag from being published or
  the `sdk-released` dispatch from reaching carespace-mobile.**

## Not a blocker here

- A breaking change to a package's public API is **not** an immediate break for
  carespace-mobile: the app is pinned to a tag and only meets the change at the
  next bump. Give it one `⚠️ Heads-up` line naming what the host must change.
- Version bumps and release notes — the `Scan release required` check owns them.
- `example/` apps, docs, and formatting / analyzer findings (CI).
