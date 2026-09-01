# Audit reporting contract

The report exists to show how the project relates to accumulated knowledge. A verdict is optional and secondary.

## Primary sections

### Where the project diverges

Include verified `GAP` and `PARTIAL` results ordered by priority, then confidence. For each item show the practice and knowledge maturity, actual project behavior, evidence paths, affected scope, impact, and actionable remediation.

### Where the project aligns

Include verified `ALIGNED` results grouped by domain. State the inspected coverage so a narrow example never reads as a project-wide guarantee.

## Coverage sections

- `UNVERIFIED`: plausible practices whose decisive evidence is external or inaccessible.
- `NOT_APPLICABLE`: compactly grouped with rationale.
- reviewer routing: fired and skipped domain reviewers with reasons.
- repository coverage: analyzed roots, exclusions, skipped/oversized files, generated areas, external services, and runtime-only boundaries.
- knowledge coverage: catalog version, catalog SHA-256, total practices, counts by knowledge state and outcome, and confirmation that every practice received one disposition.

Candidate and advisory practices remain visible but clearly labeled. Promotional claims never create a high-priority gap. If two practices conflict, report the conflict as a catalog-quality issue and avoid pretending either is an established standard.

## Optional assessment

A short assessment may summarize the most consequential patterns. Do not reduce the review to one PASS/FAIL label and do not write a Forgeward marker or initiate shipping.
