# Multitenancy rubric

| ID | Criterion | Applicability | Typical status rule | Default severity |
|---|---|---|---|---|
| `TEN-ISO-001` | Tenant context is enforced at every data-access boundary with negative isolation tests. | Confirmed multitenant systems. | `PASS` for centralized enforcement plus cross-tenant tests; `PARTIAL` for ad hoc filters; `MISSING` for tenant-tagged models without enforcement. | CRITICAL |
| `TEN-EXT-001` | Tenant-specific attributes have typed/validated limits, query/index, migration, export, and deletion behavior. | Custom tenant fields/extensions. | `PASS` for explicit model/constraints; `PARTIAL` for unconstrained JSON or metadata; `NOT_APPLICABLE` without extensions. | MEDIUM |
| `TEN-NOISY-001` | Expensive work has per-tenant concurrency/resource boundaries and observability. | Shared queues/reports/imports. | `PASS` with tenant-scoped quotas/workers; `PARTIAL` with global-only bounds; `NOT_APPLICABLE` without shared heavy work. | HIGH |
| `TEN-MIGRATE-001` | Tenant migrations are resumable, observable, safe to retry, and compatible with rolling deploys. | Per-tenant/fleet migrations. | `PASS` with direct implementation/tests; `PARTIAL` where only part is shown; `NOT_APPLICABLE` without such migrations. | HIGH |

Do not activate this domain from branding language alone. Provenance: S17.
