# Architecture

The repository root is simultaneously a Claude Code plugin and a Codex plugin. Both manifests discover the same Agent Skills under `skills/`; product-specific UI metadata stays in each skill's `agents/openai.yaml` and does not alter Claude behavior.

The audit is split into three layers:

1. `audit_evidence.py` performs bounded, deterministic, read-only file inventory, stack/surface detection, and conservative observable checks.
2. Focused domain references define applicability and judgment boundaries.
3. The audit agent confirms relevant paths and produces the final reporting contract.

The curator keeps four concerns separate:

1. gallery-dl enumerates profile reels without downloading media;
2. Moviola performs transcript/frame analysis in temporary storage;
3. the agent classifies and verifies claims;
4. `curation_state.py` validates durable provenance and enforces a separate promotion gate.

The versioned `knowledge/practices.json` catalog is the cooperation boundary. Curator proposals never rewrite audit rubrics automatically. A maintainer reviews a mature proposal, adds behavior fixtures/tests, updates the relevant focused rubric, then separately promotes the catalog entry.
