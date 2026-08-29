# Expected dependency lifecycle scripts

Reviewed 2026-08-29 against the committed npm lockfile:

- `esbuild@0.28.2` runs `node install.js` to select and verify its platform executable. This is expected for the pinned development-only build tool. Re-review its registry source, integrity, and script whenever the resolved version or script changes.
- Optional macOS dependency `fsevents@2.3.3` runs `node-gyp rebuild` for its native filesystem-events addon. It is integrity-pinned, development-only, and not installed on unsupported platforms. Re-review on any resolved version or lifecycle-script change.

CI installs from `package-lock.json`, runs the vulnerability audit, and does not approve newly introduced lifecycle scripts implicitly.
