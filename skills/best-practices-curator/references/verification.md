# Primary-document verification

Verify security, infrastructure, reliability, privacy, standards, and vendor-behavior claims immediately before proposing a rubric change because these facts can change.

## Source order

1. Standards/RFCs and government or standards-body publications.
2. Official framework, platform, database, operating-system, or vendor documentation.
3. Maintainer repository documentation/releases for the exact version.

Do not use another social post, roundup, affiliate article, search-result snippet, or model recollection as authority. Use secondary material only to discover a primary source.

Record the exact URL, document/version where available, access/verification date, what proposition it supports, and any scope limitations. If current primary documentation is unavailable or ambiguous, keep the claim `candidate`, `conflicting`, or `NOT_VERIFIABLE`.

## Conflict handling

- Prefer newer version-specific primary guidance over an older video.
- If authorities legitimately differ by client model, provider, deployment, or risk, narrow applicability rather than selecting a universal rule.
- Preserve the superseded statement and rationale in revision history.
- Never silently rewrite provenance.

Examples of claims requiring nuance include universal HMAC for browser/mobile mutations, blanket certificate pinning, IP-only rate limiting, hidden webhook URLs as authentication, changed SSH ports as a primary defense, and absolute managed-platform/VPS prescriptions.
