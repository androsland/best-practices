# Reviewer contract

This contract applies to the project mapper, every domain reviewer, the verifier, and the main audit operator.

## Model input boundary

Every model reviewer must receive a `model_input_plan` created under
`references/model-data-boundary.md`. Treat its approved paths and excerpts as a strict allowlist.
`<target-root>` is path context, not permission to scan the repository.

- Do not read an excluded, untracked, ignored, or unlisted path.
- Do not broaden a search, glob, or shell command beyond the approved scope.
- Use redacted excerpts instead of raw personal, production, credential, or private
  operational data.
- If the plan is absent, return an explicit input-boundary error without inspecting the
  target. If more evidence is necessary, return an `evidence_request` with the smallest
  path and purpose; do not open it yourself.
- Do not repeat repository material in the response when a path, line, and concise
  behavior summary are sufficient.

## Evidence model

The catalog is accumulated knowledge, not a set of filename checks. Inspect the implementation and explain how the relevant project flow behaves. Searches, inventories, manifests, dependencies, and scanners locate evidence; none proves a semantic conclusion alone.

Use exactly one outcome per assigned practice:

- `ALIGNED`: repository evidence demonstrates the practice across the stated applicable scope.
- `GAP`: direct evidence demonstrates behavior that conflicts with the practice, or a required repository-owned control is absent after sufficient scoped inspection.
- `PARTIAL`: some applicable flows align while others do not, or an important boundary is incomplete.
- `UNVERIFIED`: applicability is plausible but repository evidence cannot establish the behavior, commonly because it is runtime-, provider-, policy-, or organization-owned.
- `NOT_APPLICABLE`: the project lacks the product, stack, risk, or operational surface described by the practice.

Do not translate candidate or advisory knowledge into compliance language. Preserve each practice's `enforcement_state`, confidence, source video IDs, and authoritative references in the result.

## Required practice result

Return one object for every practice in the assigned packet:

```json
{
  "practice_id": "practice.security.server-authorization",
  "title": "Enforce authorization at a trusted boundary",
  "domain": "application-security",
  "knowledge_state": "enforceable",
  "outcome": "PARTIAL",
  "priority": "HIGH",
  "confidence": "HIGH",
  "evidence_paths": ["src/routes/orders.ts:41", "src/policies/orders.ts:12"],
  "applicable_scope": "Authenticated order read and mutation routes",
  "project_behavior": "Reads use the centralized policy; the update route checks login but not order ownership.",
  "reasoning": "A caller can select another order ID on the update path because resource authorization is absent there.",
  "coverage": "Inspected all six order routes and the shared policy module.",
  "remediation": "Apply the resource policy before the update and add a negative cross-user test.",
  "source_video_ids": ["source-id"],
  "authoritative_urls": ["https://example.invalid/primary-source"]
}
```

`priority` describes plausible project impact: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFO`. Use `INFO` for non-applicable and purely advisory observations. `confidence` is confidence in the repository conclusion, not confidence in the source practice.

## Review discipline

- Read the practice statement, applicability description, maturity, revisions, and supporting authority before judging it.
- Trace connected flows across routes, actions, data access, policies, jobs, migrations, configuration, tests, and deployment artifacts as needed.
- Distinguish executable behavior from comments, archived work, examples, fixtures, generated files, stock configuration, and future plans.
- For `ALIGNED`, state what population was covered. One route, table, or test is not proof of universal coverage.
- Treat a practice statement's material clauses as conjunctive unless the catalog explicitly says they are alternatives. Project risk may scale a control, but it does not turn an unevidenced clause into alignment. Use `PARTIAL` when only some material clauses are evidenced.
- For `GAP`, state the failure consequence or concrete divergence. A missing keyword is not a gap.
- Prefer `UNVERIFIED` when the decisive evidence lives outside the repository.
- Cite repository-relative `path:line` evidence. Do not invent line numbers.
- Never quote secret values or unnecessary personal data. Do not read untracked credential files.
- Report contradictions between catalog practices rather than silently choosing one.
- Do not edit, generate, format, install, migrate, deploy, or contact external services.

## Reviewer response

Return JSON with `reviewer`, `domains`, `practice_results`, `cross_cutting_observations`, and `coverage_limits`. `practice_results` must contain a complete object for every packet practice, including each `NOT_APPLICABLE` result. Never abbreviate, aggregate, replace records with a count, or use an ellipsis. If the response cannot contain the complete packet, return an explicit error instead of a deceptively complete-looking result. Do not return a PASS/FAIL verdict. The main operator owns synthesis and the verifier owns challenge.
