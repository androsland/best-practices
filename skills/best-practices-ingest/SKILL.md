---
name: best-practices-ingest
description: Ingest new video URLs, local videos, or incremental Instagram sources into reviewable project-practice candidates using Moviola and provenance-preserving validation. Use when adding new video-derived knowledge; not for promoting practices or auditing a repository.
---

# Best Practices Ingest

Turn source media into bounded, reviewable knowledge proposals. Resolve `<plugin-root>` from this file at `<plugin-root>/skills/best-practices-ingest/SKILL.md`. Reuse the installed Moviola skill for video understanding; do not implement or invoke a separate media-analysis pipeline.

Before processing, read the complete ingestion references:

- `<plugin-root>/skills/best-practices-curator/references/workflow.md`
- `<plugin-root>/skills/best-practices-curator/references/provenance.md`
- `<plugin-root>/skills/best-practices-curator/references/verification.md`

Use the maintained tools under `<plugin-root>/skills/best-practices-curator/scripts/` for Instagram enumeration, validation, provenance, and atomic catalog writes.

## Outcome

For each selected source:

1. Use Moviola to inspect the transcript and every returned frame, retaining source timestamps.
2. Extract atomic claims and classify each as `new`, `supporting`, `conflicting`, `obsolete`, or `promotional`.
3. Verify consequential security, reliability, infrastructure, privacy, and vendor-behavior claims against current primary documentation.
4. Submit proposed fields only through `curation_state.py propose`; never hand-edit model-generated catalog content.
5. Record the source and linked claim IDs only after proposal validation succeeds. On two bounded extraction failures, record the source as failed and leave the catalog unchanged.
6. Remove temporary media, audio, frames, captions, and transcripts unless the user explicitly asked to retain a named artifact.

New material enters as `candidate` or `advisory`. Ingestion never promotes a practice to `enforceable`. Use `$best-practices-curator` for later human-reviewed revision, merging, deprecation, or promotion.

Never access browser cookies without invocation-local consent, install dependencies without approval for the exact command, retain secret or personal data unnecessarily, or treat repeated social claims as independent authority.
