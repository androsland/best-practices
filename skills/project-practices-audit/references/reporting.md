# Audit reporting contract

## Statuses

- `PASS`: repository evidence satisfies the check's stated criterion.
- `MISSING`: an applicable, required artifact or control is absent and repository scope is sufficient to establish that absence.
- `PARTIAL`: evidence shows only part of the criterion, inconsistent coverage, or a material weakness.
- `NOT_APPLICABLE`: the stack/product surface that makes the check relevant is absent.
- `NOT_VERIFIABLE`: repository evidence cannot establish the control, commonly because it is runtime-, provider-, policy-, or organization-owned.

`MISSING` and `PARTIAL` are failing statuses. `NOT_VERIFIABLE` is an explicit coverage gap, not a pass. Promotional/advisory checks never contribute to failure counts.

## Severity and confidence

Use `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFO`. Severity describes plausible impact for this project, not generic fear. Use `INFO` for `NOT_APPLICABLE`, promotional, or subjective advice.

Confidence is `HIGH`, `MEDIUM`, or `LOW`:

- `HIGH`: direct, project-specific evidence establishes the finding.
- `MEDIUM`: multiple signals support the finding but relevant runtime/context is missing.
- `LOW`: weak or ambiguous signals; prefer `NOT_VERIFIABLE` over a speculative failure.

## Finding shape

```json
{
  "check_id": "SEC-AUTHZ-001",
  "domain": "application-security",
  "status": "PARTIAL",
  "severity": "HIGH",
  "confidence": "HIGH",
  "evidence_paths": ["src/routes/admin.ts:18", "src/auth/policy.ts:7"],
  "rationale": "The route checks authentication but no resource-level authorization is visible.",
  "remediation": "Authorize the requested resource server-side before the operation and add a negative cross-user test."
}
```

For absence, evidence paths name the closest relevant manifest/config plus the searched scope, for example `package.json` and `(searched .github/workflows/)`. Do not invent line numbers. Findings must be individually actionable; avoid a single vague umbrella failure.

## Summary

Report target, detected stack, analyzed domains, counts by status/severity, prioritized remediation, and coverage limitations. Include skipped candidate-file counts from `evidence_budget`; never imply a bounded scan covered files it skipped. The overall verdict is:

- `PASS` when no applicable enforceable check is `MISSING` or `PARTIAL`;
- `NEEDS_WORK` otherwise.

Never let advisory/promotional findings affect the verdict.
