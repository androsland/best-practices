# Recovery runbook

Critical PostgreSQL data has an RPO of 15 minutes and an RTO of 60 minutes. Base backups and WAL archiving are retained in a separate account.

The restore drill restores into an isolated environment, runs migrations and permission checks, exercises critical reads/writes, and records measured RTO. The last recovery exercise completed within target.
