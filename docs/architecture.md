# Architecture

The repository root is simultaneously a Claude Code and Codex plugin. Both manifests discover the same skills and authoritative reviewer definitions.

## Knowledge lifecycle

1. Moviola supplies timestamped transcript and visual evidence from a video.
2. `best-practices-ingest` extracts atomic claims and submits them through bounded validation.
3. `best-practices-curator` preserves provenance, resolves duplicates/conflicts, verifies consequential claims, and controls later promotion.
4. `knowledge/practices.json` remains the canonical, versioned catalog. Audits record its SHA-256.

Installed plugin caches are immutable delivery artifacts. Knowledge updates happen in this source repository and reach installed users through a validated reinstall or release.

## Audit lifecycle

1. Before model processing, the operator discloses the provider/model and known or
   unknown retention/training posture, obtains invocation-specific confirmation, and
   records a minimized `model_input_plan` outside the target.
2. `repository_inventory.py` produces a bounded file/path inventory with no practice
   status or verdict; credentials, raw production records, and sensitive or unapproved
   paths remain outside model inputs.
3. The project-mapper agent reads only approved architecture evidence and builds a
   shared architecture, trust-boundary, and critical-flow model.
4. The main operator routes complete catalog packets and domain-sized evidence bundles
   to only the relevant reviewers.
5. Reviewers inspect connected implementation flows within their allowlists and account
   for every assigned practice as aligned, divergent, partial, unverifiable, or not
   applicable.
6. The verification reviewer challenges every gap/partial result and broad positive
   claim using only approved cited evidence.
7. The operator reports two primary evidence lists—divergence and alignment—plus catalog
   and repository coverage, including every privacy-driven exclusion.

Reviewer models are explicitly pinned rather than inherited: Claude plugin agents use Sonnet with medium effort; Codex launches use `gpt-5.6-terra`, medium reasoning, and isolated context. A Git workspace snapshot/check verifies the read-only contract.

## Forgeward boundary

Best Practices is whole-repository, knowledge-driven, and advisory. Forgeward Gate remains diff-scoped and enforceable. Mature, objective, low-noise controls may later be promoted into Forgeward through a separate reviewed contribution; adding a video never changes a shipping gate automatically.
