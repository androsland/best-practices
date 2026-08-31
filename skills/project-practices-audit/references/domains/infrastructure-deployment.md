# Infrastructure and deployment rubric

| ID | Criterion | Applicability | Typical status rule | Default severity |
|---|---|---|---|---|
| `INF-DEPLOY-001` | Deployment is reproducible and has a documented rollback/recovery path. | Deployable services/apps. | `PASS` with versioned pipeline/IaC and rollback; `PARTIAL` with deploy only; external pipeline may be `NOT_VERIFIABLE`. | HIGH |
| `INF-SECRET-001` | Runtime secrets come from an appropriate secret store/injection path and are rotatable. | Deployable systems with secrets. | Repository can establish unsafe committed/default secrets; provider-side safety is often `NOT_VERIFIABLE`. | CRITICAL |
| `INF-NET-001` | Public exposure is limited to required services; stateful/admin surfaces are private or tightly restricted. | Networked deployments. | Use IaC/compose/k8s evidence; runtime firewall state outside repo is `NOT_VERIFIABLE`. | HIGH |
| `INF-PATCH-001` | Base images/runtimes and hosts have an update/replacement strategy. | Containers, VMs, VPS. | `PASS` for automated maintained rebuild/update evidence; `PARTIAL` for floating/obsolete bases; provider-only behavior may be `NOT_VERIFIABLE`. | HIGH |
| `INF-OBS-001` | Availability, capacity, auth failures, and critical service health have logs/metrics/alerts. | Production services. | Config supports status; external observability without config is `NOT_VERIFIABLE`. | HIGH |
| `INF-TLS-001` | Public traffic uses TLS with renewal/termination ownership understood. | Public services. | `PASS` from managed/IaC config; local dev HTTP is not a failure; runtime-only setup is `NOT_VERIFIABLE`. | HIGH |

Managed platform versus VPS is a contextual tradeoff. Cost, “best platform,” and fixed-price claims are advisory and never affect the verdict. Provenance: S03, S15; Ubuntu OpenSSH/UFW/automatic-updates guidance.
