---
name: project-practices-audit
description: Perform a read-only, evidence-backed whole-project engineering-practices audit. Use for project/repository audits covering coding and AI-agent workflows, application security, data reliability, multitenancy, infrastructure, deployment, product onboarding, or AI usage; not for diff-only review or automatic remediation.
---

# Project Practices Audit

Audit the requested project without changing it. Detect its stack and product shape first, then evaluate only applicable checks. Do not install dependencies, contact production systems, access secrets, or write into the target. Resolve bundled scripts relative to the directory containing this `SKILL.md`; never assume the target project's working directory contains them.

## Workflow

1. Resolve the target root. Run `python3 scripts/audit_evidence.py <root> --format json` from this skill directory, or use the absolute script path. Treat the output as evidence, not as a substitute for inspecting relevant files.
2. Read [references/stack-detection.md](references/stack-detection.md) and select domain references from `references/domains/` using the detected signals. Always inspect coding/AI workflow and AI-usage domains; mark individual checks `NOT_APPLICABLE` when the project has no relevant surface.
3. Inspect every evidence path needed to confirm or challenge the deterministic observations. Never infer runtime or production configuration solely from a template, dependency, filename, or absence of a file.
4. Apply [references/reporting.md](references/reporting.md). Report every selected check as exactly `PASS`, `MISSING`, `PARTIAL`, `NOT_APPLICABLE`, or `NOT_VERIFIABLE`.
5. End with prioritized remediation and a coverage statement naming excluded, inaccessible, or runtime-only surfaces.

## Invariants

- Every finding includes check ID, domain, status, severity, confidence, evidence paths, rationale, and actionable remediation. `PASS` and non-applicable findings still carry those fields; use `None` for remediation when no action is needed.
- Missing evidence is not automatically a failure. Use `NOT_VERIFIABLE` when proof may live outside the repository or requires runtime access. Use `MISSING` only when the rubric requires an artifact and the searched project scope is sufficient to establish absence.
- Promotional, subjective, aesthetic, cost, popularity, productivity-multiplier, or one-size-fits-all product recommendations are advisory. They must never produce a failing status or affect the audit verdict.
- Do not expose secret values. Evidence may name a file and line, but redact credentials, tokens, personal data, and sensitive operational values.
- Do not claim exhaustive security assurance. This is a practices audit over available project evidence.

## References

- Always read [references/reporting.md](references/reporting.md) and [references/stack-detection.md](references/stack-detection.md).
- Read only the applicable files in [references/domains/](references/domains/): `coding-ai.md`, `application-security.md`, `data-reliability.md`, `multitenancy.md`, `infrastructure-deployment.md`, `product-onboarding.md`, and `ai-usage.md`.
- The curator owns changes to `knowledge/practices.json`; the audit may read that catalog for provenance but must not update it.
