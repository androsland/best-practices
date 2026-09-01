---
name: best-practices-audit
description: Run a read-only, whole-repository, knowledge-driven best-practices review with contextual specialist agents. Use when the user wants to compare a project against the accumulated practice catalog and receive evidence-backed gaps and alignments; not for diff-only review, shipping enforcement, or automatic remediation.
---

# Best Practices Audit

Act as the main operator for a read-only whole-repository review. The catalog is the knowledge source, deterministic scripts are evidence helpers, and specialist agents make contextual judgments. Never let a keyword or file-presence heuristic decide applicability, adherence, or the overall result.

## Resolve the plugin and target

Derive `<plugin-root>` from this loaded file: it is `<plugin-root>/skills/best-practices-audit/SKILL.md`. Resolve the requested repository as `<target-root>`. Do not install dependencies, contact production systems, access secret values, or write inside `<target-root>`.

Read these contracts completely before launching reviewers:

- `<plugin-root>/references/reviewer-contract.md`
- `<plugin-root>/references/reporting-contract.md`
- `<plugin-root>/references/model-data-boundary.md`

## Model data preflight

Before reading repository files into any model context or launching the project mapper,
complete the model-data-boundary protocol. This is a hard launch gate:

1. Disclose the active provider and exact reviewer model, what repository-derived data
   the mapper and reviewers will process, and the retention/training posture established
   by the active product or workspace. State unknown parts as unknown; never infer them
   from this plugin or from generic account assumptions.
2. Obtain invocation-specific user confirmation for that disclosed processing boundary.
   The audit request alone is not confirmation of an undisclosed provider or policy.
3. Use local deterministic inspection to exclude credentials, keys, raw production
   records, untracked/ignored files, and likely personal or private operational data.
   Never print secret values or raw matches.
4. Create a `model_input_plan` outside `<target-root>` containing only approved tracked
   paths or bounded redacted excerpts, excluded categories, provider/model/policy facts,
   confirmation, and coverage impact. If sensitive material is necessary, stop and get
   specific confirmation as prescribed by the protocol; always keep credential values
   excluded.

Do not launch a mapper or reviewer without this plan. If the user declines, the provider
or policy cannot be disclosed, or safe minimization is not possible, stop and report the
coverage boundary without sending repository contents to another model.

Run the bounded inventory helper once:

```bash
python3 <plugin-root>/skills/best-practices-audit/scripts/repository_inventory.py <target-root> --format json
python3 <plugin-root>/skills/best-practices-catalog/scripts/catalog_query.py <plugin-root>/knowledge/practices.json summary
```

The inventory contains paths and candidate signals only. It must not be quoted as proof that a feature exists or that a practice is followed.

## Read-only guard

For a Git repository, snapshot the existing state outside the target before spawning reviewers:

```bash
python3 <plugin-root>/skills/best-practices-audit/scripts/workspace_guard.py snapshot <target-root> > <outside-target-snapshot.json>
```

After every reviewer finishes, run `workspace_guard.py check <target-root> <outside-target-snapshot.json>`. If it reports a change, halt the audit, identify the changed paths, and do not delete or repair them. The user owns pre-existing changes and any reviewer-created files.

## Map, route, and review

1. Launch the project mapper first with the inventory and the architecture-relevant
   allowlist or redacted excerpts from `model_input_plan`. Passing `<target-root>` is for
   path resolution and does not authorize an unrestricted repository scan. The mapper
   returns the architecture, trust boundaries, critical flows, external systems, and
   coverage limits. It does not assess practices.
2. Load the packet summaries, then use the map to conditionally launch reviewers. Fire a reviewer when any practice in its packet may apply; a project does not need the packet's headline surface. For example, a dependency-only library can activate the application-security reviewer for dependency supply-chain knowledge, and open-source dependencies can activate governance for license obligations. When uncertain, fire the reviewer and let it assign per-practice applicability. Route catalog domains as follows:
   - application security: `application-security`, `multitenancy`
   - reliability and data: `data-reliability`, `database-performance`
   - infrastructure: `infrastructure-deployment`
   - engineering: `coding-ai`, `coding-workflow`, `api-design`
   - AI: `ai-engineering`, `ai-usage`
   - product: every `product-*` domain and `promotional`
   - governance: `governance`
   The exact reviewer names are `application-security`, `reliability`, `infrastructure`, `engineering`, `ai`, `product`, and `governance`; do not invent alternate routing categories. For a skipped reviewer, the main operator assigns every practice in that packet `NOT_APPLICABLE` using the mapper's project-surface evidence and a specific rationale. Do not silently omit skipped packets.
3. Generate each reviewer's complete knowledge packet with `catalog_query.py packet --reviewer <reviewer-name>`. A routed reviewer must account for every practice in its packet exactly once, even when most are not applicable.
4. Run selected domain reviewers in parallel. Give each only the shared map, its packet,
   and the smallest domain-specific allowlist or redacted excerpt bundle needed to trace
   actual project flows. It must not rescan the whole repository. An `evidence_request`
   for another path returns to the main operator for a new privacy/minimization decision;
   the reviewer does not open it directly. Regex searches may locate candidates; they
   never establish a conclusion by themselves. Validate each returned packet with
   `catalog_query.py <catalog> coverage <reviewer-results.json> --reviewer
   <reviewer-name>`; reject abbreviated or structurally incomplete handoffs.
5. Give the verification reviewer every proposed `GAP`, `PARTIAL`, broad `ALIGNED`
   claim, the reviewer firing/skip decision, and only the approved cited evidence needed
   to challenge them. It must not start a new whole-repository search. The main operator
   resolves conflicts from evidence rather than reviewer seniority.
6. Consolidate the corrected reviewer results in a temporary file outside the target and run `catalog_query.py <catalog> coverage <results.json>`. Do not report completion while any practice ID is missing, duplicated, unknown, or assigned an invalid outcome.

Do not create one agent per practice. Domain reviewers need enough connected repository context to trace behavior across boundaries.

## Runtime and model policy

Reviewer model selection is explicit and never inherited from the parent:

- Claude Code: use the matching plugin agent type under `agents/`. Its definition pins `model: sonnet` and `effort: medium`.
- Codex: use the collaboration/subagent facility with `model: "gpt-5.6-terra"`, `reasoning_effort: "medium"`, and `fork_turns: "none"` on every launch. Tell the isolated agent to read the complete authoritative rubric at `<plugin-root>/agents/<agent-file>.md`; pass `<plugin-root>`, `<target-root>` for path resolution, the applicable `model_input_plan` scope, the minimized project map or review bundle, the knowledge packet, and the read-only requirement.
- Other harnesses: use an explicitly documented balanced/medium reviewer mapping. If the harness cannot guarantee isolated read-only reviewers at the requested model tier, stop and report that limitation instead of silently running a different architecture.

The mapper and reviewers use medium reasoning because repository-flow analysis is semantic work. Low-tier deterministic work belongs in the inventory and catalog scripts.

## Report

Use the reporting contract. The two primary sections are:

1. **Where the project diverges** — verified `GAP` and `PARTIAL` observations, prioritized by plausible impact.
2. **Where the project aligns** — verified `ALIGNED` observations with explicit coverage scope.

Then include coverage gaps (`UNVERIFIED`), non-applicable practices, analyzed/skipped file limits, reviewer routing, catalog revision/hash, and practice counts. A short overall assessment is optional and must never replace the evidence lists.

## Invariants

- The main operator and every reviewer are read-only.
- Every catalog practice receives exactly one disposition: `ALIGNED`, `GAP`, `PARTIAL`, `UNVERIFIED`, or `NOT_APPLICABLE`.
- Positive alignment requires coverage evidence, not one favorable example.
- Repository absence supports a gap only when the searched scope is sufficient and the practice requires a repository-owned artifact.
- Candidate and advisory knowledge may produce observations, but the report must show its maturity and must not present it as an enforced standard.
- Never expose credentials, personal data, private operational values, or raw scanner matches. Cite a redacted path and line only.
- A target path is not blanket authorization to read it. Every model receives only the
  invocation-approved, minimum-necessary evidence scope from `model_input_plan`.
- Do not claim exhaustive security assurance or complete system understanding. Name external, generated, inaccessible, skipped, and runtime-only surfaces.
- Never modify the target or remediate findings during the audit.
