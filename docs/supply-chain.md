# Supply-chain review

Reviewed 2026-08-29:

- `gallery-dl` is an optional, user-approved external CLI installed from its canonical PyPI project at version `1.32.9` (GPL-2.0). Offered pipx, uv, and pip commands pin that exact release. The wrapper disables ambient configuration, connects only through gallery-dl to the user-selected Instagram profile, reads browser cookies only with invocation-local consent, and retains enumeration metadata rather than media. Any version change requires a fresh source, license, network, cookie-permission, and output review.
- Root CI pins `actions/checkout` v4.3.0 to commit `08eba0b27e820071cde6df949e0beb9ba4906955` (MIT). The workflow grants only `contents: read`; the action communicates with GitHub to fetch the repository. Any SHA update requires reviewing the upstream release and bundled code.

Fixture npm dependencies remain governed by `fixtures/secure-saas/docs/supply-chain-review.md` and committed lockfile integrity values.
