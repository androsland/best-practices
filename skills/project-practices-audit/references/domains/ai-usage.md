# AI usage rubric

| ID | Criterion | Applicability | Typical status rule | Default severity |
|---|---|---|---|---|
| `AI-DATA-001` | AI data flows identify providers, sensitive inputs, retention, and user disclosure/consent where relevant. | Products or workflows sending project/user data to AI services. | `PASS` with explicit documented controls; `PARTIAL` with provider calls but gaps; local inference claims require telemetry/runtime confirmation. | HIGH |
| `AI-KEY-001` | Model/provider credentials stay server-side and are scoped/rotatable. | AI APIs requiring credentials. | `MISSING` for embedded/committed client credentials; secure external configuration may be `NOT_VERIFIABLE`. | CRITICAL |
| `AI-OUTPUT-001` | Consequential model output is validated, bounded, and reviewed before side effects. | AI that writes, deploys, bills, authorizes, deletes, or affects users. | `PASS` with schemas/approval/idempotency tests; `PARTIAL` for weak parsing; `NOT_APPLICABLE` for non-consequential suggestions. | HIGH |
| `AI-EVAL-001` | Representative evals/regression checks exist for product-critical AI behavior. | Product-critical AI features. | `PASS` with executable evals and fixtures; `PARTIAL` for ad hoc examples; `NOT_APPLICABLE` for incidental developer tooling. | MEDIUM |
| `AI-SUPPLY-001` | Skills, plugins, MCP servers, hooks, and install scripts are pinned/reviewed with bounded permissions. | Projects distributing or configuring agent extensions. | `PASS` with explicit provenance/review; `PARTIAL` for unpinned external components; absence of extensions is `NOT_APPLICABLE`. | HIGH |
| `AI-PROMO-001` | Productivity, cost, model-superlative, popularity, and watermark claims remain advisory until reproduced and verified. | When such claims appear. | Always `NOT_VERIFIABLE` or `NOT_APPLICABLE`, severity `INFO`; never affects verdict. | INFO |

Inventorying an AI SDK is not proof of safety. Inspect actual boundaries and distinguish local processing from API audio/media upload. Provenance: S02, S05, S06, S08, S09, S14, S16, S20, S23, S25, S27.
