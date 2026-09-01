# Architecture

The repository root is simultaneously a Claude Code and Codex plugin. Both manifests discover the same skills and authoritative reviewer definitions.

## Knowledge lifecycle

1. Moviola supplies timestamped transcript and visual evidence from a video.
2. `best-practices-ingest` extracts atomic claims and submits them through bounded validation.
3. `best-practices-curator` preserves provenance, resolves duplicates/conflicts, verifies consequential claims, and controls later promotion.
4. `knowledge/practices.json` remains the canonical, versioned catalog. Audits record its SHA-256.

Installed plugin caches are immutable delivery artifacts. Knowledge updates happen in this source repository and reach installed users through a validated reinstall or release.

## Audit lifecycle

1. `repository_inventory.py` produces a bounded file/path inventory with no practice status or verdict.
2. The project-mapper agent reads the repository and builds a shared architecture, trust-boundary, and critical-flow model.
3. The main operator routes complete catalog packets to only the relevant domain reviewers.
4. Reviewers inspect connected implementation flows and account for every assigned practice as aligned, divergent, partial, unverifiable, or not applicable.
5. The verification reviewer challenges every gap/partial result and broad positive claim.
6. The operator reports two primary evidence lists—divergence and alignment—plus catalog and repository coverage.

Reviewer models are explicitly pinned rather than inherited: Claude plugin agents use Sonnet with medium effort; Codex launches use `gpt-5.6-terra`, medium reasoning, and isolated context. A Git workspace snapshot/check verifies the read-only contract.

## Forgeward boundary

Best Practices is whole-repository, knowledge-driven, and advisory. Forgeward Gate remains diff-scoped and enforceable. Mature, objective, low-noise controls may later be promoted into Forgeward through a separate reviewed contribution; adding a video never changes a shipping gate automatically.
