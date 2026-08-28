# Product onboarding and retention rubric

These are product-quality checks, not security controls. Evidence often lives in analytics or experiments outside the repository; use `NOT_VERIFIABLE` rather than inventing a failure.

| ID | Criterion | Applicability | Typical status rule | Default severity |
|---|---|---|---|---|
| `PROD-VALUE-001` | A meaningful first-value event is explicitly defined and instrumented. | End-user products with signup/onboarding. | `PASS` with a named event and implementation; `PARTIAL` for generic onboarding-complete tracking; otherwise `NOT_VERIFIABLE`. | MEDIUM |
| `PROD-FLOW-001` | Onboarding lets users perform the core action without unnecessary blocking steps. | End-user onboarding flows. | Requires direct route/UI evidence; subjective polish remains advisory. | LOW |
| `PROD-DISCLOSE-001` | Advanced complexity is progressively available without hiding essential capability. | Products with advanced features. | Usually qualitative `PASS`/`PARTIAL` with direct UI evidence; never fail on arbitrary session counts. | LOW |
| `PROD-REENGAGE-001` | Re-engagement is tied to created value and respects consent/preferences/time zones/data minimization. | Products sending lifecycle notifications. | `PASS` with trigger plus preference/privacy controls; `PARTIAL` if controls are incomplete; `NOT_APPLICABLE` without re-engagement. | MEDIUM |
| `PROD-MEASURE-001` | Onboarding/retention measurement distinguishes first value and retained use. | Products actively measuring onboarding. | Repository SDK presence alone is insufficient; external dashboards are `NOT_VERIFIABLE`. | LOW |

“First value in 60 seconds” is a hypothesis, not a universal threshold. Provenance: S13.
