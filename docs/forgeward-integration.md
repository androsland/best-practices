# Future Forgeward integration candidates

Forgeward is intentionally unchanged in this version. Project Practices remains independently installable and testable; any future contribution should preserve Forgeward's existing scope and enforcement model.

## Potential `forgeward:audit` contributions

These whole-repository checks are plausible only after broader stack fixtures, low false-positive rates, authoritative provenance, and stable remediation language:

| Candidate | Why deep-audit shaped | Readiness |
|---|---|---|
| Server/data-layer authorization coverage and negative object/tenant tests | Requires tracing routes, policies, and data access across the project. | Candidate; current collector intentionally returns `NOT_VERIFIABLE` for semantic coverage. |
| Supabase RLS, grants, elevated-key boundaries, views/functions, and role tests | Crosses migrations, clients, functions, and test behavior. | Relatively mature for common layouts; broaden fixtures before contribution. |
| Webhook authenticity, raw-body ordering, replay/idempotency, and retry handling | Requires lifecycle reasoning across handler, persistence, and async work. | Mature for Stripe-shaped examples; needs additional providers. |
| RPO/RTO, backup/PITR topology, restore drills, and recovery observability | Mostly whole-system evidence with common off-repository gaps. | Keep conservative `NOT_VERIFIABLE`; not ready to enforce universally. |
| Multitenant isolation, custom-extension design, noisy-neighbor budgets, and fleet migrations | Requires schema/request/queue/migration correlation. | Candidate; current knowledge entry is not yet promoted. |
| AI/MCP/skill supply-chain permissions and data-flow review | Crosses plugin manifests, hooks, network destinations, prompts, and secrets. | Candidate; needs ecosystem-specific provenance rules. |

## Potential fast `forgeward:gate` checks

These could be diff-scoped only when the changed files activate the relevant surface and the check remains fast and deterministic:

| Candidate | Diff activation | Gate behavior |
|---|---|---|
| New webhook handler lacks recognizable signature verification or places side effects before it | Added/changed webhook route | Fail only with direct ordering evidence; otherwise request deep review. |
| New exposed Supabase table migration lacks RLS enablement/policy companion | Changed Supabase SQL migration | Fail when exposure is direct and absence is established within the migration set. |
| Elevated/service credentials appear in browser/mobile code | Changed client bundle source/config | Fail on high-confidence identifiers while redacting values. |
| New third-party skill, MCP server, hook, or install script lacks pinned provenance/review metadata | Changed extension manifest/config | Warn/fail according to Forgeward's supply-chain policy after false-positive testing. |
| Migration introduces a tenant identifier without a negative isolation test change | Changed schema/policy plus tests | Request review; fail only once framework-specific evidence is reliable. |
| Consequential AI side effect is added without schema validation/approval/idempotency boundary | Changed AI call path plus mutation/deploy/billing code | Initially advisory because semantic tracing is difficult in a fast gate. |

Product-onboarding preferences, managed-platform versus VPS choices, exact restore-drill cadence, universal WAF/pinning/HMAC prescriptions, cost claims, aesthetics, popularity, and productivity multipliers should not become Forgeward failures.
