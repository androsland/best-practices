# Expected dependency lifecycle scripts

Reviewed 2026-08-29 against the committed npm lockfile:

- `esbuild@0.28.2` runs `node install.js` to select and verify its platform executable. This is expected for the pinned development-only build tool. Re-review its registry source, integrity, and script whenever the resolved version or script changes.
- Optional macOS dependency `fsevents@2.3.3` runs `node-gyp rebuild` for its native filesystem-events addon. It is integrity-pinned, development-only, and not installed on unsupported platforms. Re-review on any resolved version or lifecycle-script change.

CI installs from `package-lock.json`, runs the vulnerability audit, and does not approve newly introduced lifecycle scripts implicitly.

## Optional native image dependencies

`next@16.3.3` declares optional Sharp platform packages. The committed lockfile therefore records prebuilt `@img/sharp-*` packages and `@img/sharp-libvips-*`; the latter are licensed `LGPL-3.0-or-later`. This fixture does not use Next image optimization, and redistribution of those optional native packages is not approved by this review.

The project-level `.npmrc` sets `omit=optional`, so fixture installs and build artifacts exclude Sharp, libvips, and all other optional dependencies. Removing that setting or adding image optimization requires a fresh license and redistribution review, any required compliance materials, and an update to this document before release.
