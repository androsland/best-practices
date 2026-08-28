# Data reliability and multi-tenancy

## Disaster recovery is a business requirement

S12’s strongest point is that the backup schedule must follow acceptable loss and downtime, not provider defaults (`S12 00:20–02:06`).

### Define the targets first

- **RPO — Recovery Point Objective:** the maximum acceptable amount of lost data.
- **RTO — Recovery Time Objective:** the maximum acceptable time to restore service.

These targets determine backup frequency, replication, retention, restore automation, staffing, and cost.

### Use the right recovery mechanism

- Nightly snapshots can imply nearly a day of data loss; they may be acceptable only when the RPO permits it.
- For PostgreSQL workloads with a tighter RPO, combine base backups with continuous WAL archiving so recovery can stop near a chosen time.
- Retain backups separately from the primary failure domain and protect them from accidental deletion or compromised credentials.
- Monitor failed backups and gaps in the WAL/archive chain.

PostgreSQL documents how base backups plus archived WAL support [continuous archiving and point-in-time recovery](https://www.postgresql.org/docs/17/continuous-archiving.html).

### Prove that restoration works

S12 recommends at least quarterly restore tests (`01:07–01:41`). Choose cadence from risk and change frequency, then:

1. Restore into a clean isolated environment.
2. Verify integrity, migrations, permissions, and application startup.
3. Exercise critical read/write paths.
4. Measure actual recovery time and compare it with RTO.
5. Record gaps, owners, commands, dependencies, and escalation steps.
6. Update the runbook and repeat after material infrastructure changes.

A backup is an input. A tested, timed, documented restoration process is the recovery capability.

## Keep tenant-specific needs out of the shared core

S17 describes a common SaaS problem: one customer’s custom field or heavy report degrades a shared system (`S17 00:00–00:45`). The recommended architecture has three lanes.

### 1. Extension data

Keep stable, widely shared fields in the core schema. Put sparse tenant-specific attributes into a deliberate extension model, such as:

- a typed metadata/attribute table;
- JSONB with validation and constrained indexing;
- a dedicated tenant schema or service when isolation requirements justify it.

Do not choose JSON merely to avoid schema design. Define types, limits, validation, query patterns, retention, indexing, and migration behavior. Measure join and index costs before promising arbitrary custom fields.

### 2. Workload isolation

- Route expensive reports and imports through queues or tenant-scoped workers.
- Apply per-tenant concurrency, CPU/time, storage, and rate budgets.
- Instrument usage so noisy-neighbor effects are visible.
- Consider dedicated compute or storage only for tenants whose performance, regulatory, or contractual needs justify it.

### 3. Migration separation

- Keep core-schema changes backward compatible during rolling deployment.
- Version extension data and migrate it per tenant when possible.
- Make migrations resumable, observable, and safe to retry.
- Test representative large tenants and rollback/roll-forward paths.

## Decision checklist

Before accepting a tenant-specific feature:

- Is it truly unique, or likely to become a core product capability?
- How will it be validated and queried?
- Which indexes or workers does it need?
- Can one tenant exhaust shared resources?
- How will the extension be backed up, restored, exported, and deleted?
- Can it be migrated without fleet-wide downtime?

## Source synthesis

- S12: PITR, restore drills, RTO, and RPO.
- S17: extension storage, workload isolation, and tenant-scoped migration strategy.
