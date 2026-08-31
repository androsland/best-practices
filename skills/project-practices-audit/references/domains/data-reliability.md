# Data reliability rubric

| ID | Criterion | Applicability | Typical status rule | Default severity |
|---|---|---|---|---|
| `REL-RPO-001` | RPO and RTO are defined for critical durable data. | Stateful production systems. | `PASS` with owned, measurable targets; `MISSING` for a production runbook with no targets; otherwise `NOT_VERIFIABLE` when policy is external. | HIGH |
| `REL-BACKUP-001` | Backup/PITR configuration matches the stated RPO and is isolated from the primary failure domain. | Stateful production systems. | IaC/config can support `PASS`/`PARTIAL`; provider-console-only setup is `NOT_VERIFIABLE`. | CRITICAL |
| `REL-RESTORE-001` | Restoration is tested, timed, and documented against RTO. | Systems requiring recovery. | `PASS` with recent drill evidence/runbook automation; `PARTIAL` for an untested runbook; `NOT_VERIFIABLE` when records are external. | HIGH |
| `REL-MIGRATE-001` | Schema/data migrations are reviewable, retry-safe where needed, and exercised in CI or staging. | Projects with migrations. | `PASS` with migration tooling plus checks; `PARTIAL` without representative validation; `NOT_APPLICABLE` without schema/data migrations. | HIGH |
| `REL-OBS-001` | Backup failures, archive gaps, queue failures, and critical data-path errors are observable. | Corresponding stateful components. | `PASS` with alert config/tests; absent provider-side config is `NOT_VERIFIABLE`. | HIGH |

A `backup` script name alone is insufficient. A backup is not a demonstrated recovery capability without restore evidence. Provenance: S12 and PostgreSQL continuous-archiving documentation.
