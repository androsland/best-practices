---
name: best-practices-curator
description: Review, reconcile, revise, merge, deprecate, or promote existing project-practice knowledge with preserved provenance. Use for catalog maintenance after ingestion; not for watching new videos or auditing a repository.
---

# Best Practices Curator

Maintain the canonical catalog without silently converting source claims into standards. Resolve bundled scripts relative to this skill directory and read [references/provenance.md](references/provenance.md) plus [references/verification.md](references/verification.md) before changing knowledge.

## Workflow

1. Inspect the target practice's statement, applicability, knowledge state, sources, authoritative references, and full revision history.
2. Compare duplicates and conflicts semantically. Repetition does not raise confidence; narrower applicability is often more accurate than choosing one universal claim.
3. Verify consequential or time-sensitive claims against current primary sources before revising or promoting them.
4. Perform changes only through `scripts/curation_state.py`; it validates untrusted text, preserves revision history, and atomically writes a valid catalog. Do not hand-edit model-derived catalog changes.
5. Validate the complete catalog after every operation.

Available operations include `revise-practice`, `merge-practice`, `reclassify-domain`, `repair-references`, and `promote`. Promotion requires explicit reviewed confirmation, current authority where consequential, and test evidence covering aligned, divergent/partial, and non-applicable behavior.

## Invariants

- Ingestion and curation are separate. Use `$best-practices-ingest` for new media.
- Promotional and subjective claims remain advisory.
- Preserve source IDs, authority, applicability, confidence, and append-only revision history. Privacy deletion is the documented exception.
- A practice becoming `enforceable` means its assessment criteria are mature enough for strong audit language; it does not automatically become a Forgeward shipping gate.
- Do not modify audit reviewer rubrics merely because a candidate was added. Promote hardened deterministic controls into Forgeward only through a separate reviewed contribution.
