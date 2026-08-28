# Provenance and claim classification

## Claim classes

- `new`: materially absent from the catalog. Create a candidate only.
- `supporting`: independently restates or demonstrates an existing practice. Append provenance; do not raise confidence solely because similar videos repeat it.
- `conflicting`: contradicts a current practice or applicability boundary. Preserve both positions and require authoritative review before changing the rubric.
- `obsolete`: describes superseded product behavior, documentation, version, pricing, or practice. Preserve historical provenance but do not enforce it.
- `promotional`: subjective, superlative, income/cost/productivity/popularity claim, unverified product endorsement, or aesthetic preference. Keep advisory; it can never fail an audit.

## Required practice fields

Each practice has a stable ID, domain, title, statement, enforcement state (`candidate`, `advisory`, or `enforceable`), applicability text/signals, confidence, source video IDs, authoritative references, verification date, and append-only revision history. Each revision records date, change type, reason, source IDs, and authoritative references used.

Source IDs should be platform-stable identifiers when available. For local media, use a SHA-256 digest of the file bytes prefixed with `local-sha256:`; never use a filename alone as identity.

## Promotion gate

A newly extracted claim may only enter as `candidate` or `advisory`. A later reviewed revision may set `enforceable` when:

1. the claim is objective and auditable;
2. applicability and non-applicable cases are explicit;
3. failure impact justifies enforcement;
4. current primary authority supports security, infrastructure, or reliability claims;
5. the check has reliable evidence requirements and conservative `NOT_VERIFIABLE` behavior;
6. tests cover at least pass, fail/partial, and non-applicable behavior.

Popularity, repetition, a creator's confidence, or a product demo never satisfies this gate.
