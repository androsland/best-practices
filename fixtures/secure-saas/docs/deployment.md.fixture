# Deployment and rollback

Terraform and the release workflow deploy immutable images. Rollback selects the previous image revision and pauses if a data migration is not backward compatible.

## Security migration rollout

1. Deploy application code that sets `app.workspace_id` for every project read and write. Verify anonymous, cross-workspace, same-workspace, and background-worker behavior while RLS remains disabled.
2. Apply the standard migrations, including `202608280000_projects_workspace_index.sql` and `202608280001_workspace_policies.sql`. The supporting index is built without blocking writes and the policies remain dormant during the mixed-version window.
3. Drain every application version that does not set the request context. The phase-2 RLS migration is deliberately stored outside `supabase/migrations`, so `supabase db push` cannot cross this boundary. After the drain and role-level checks, apply exactly that file and repeat the checks:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/release-phases/phase-2/202608280002_enable_projects_rls.sql
```

The phase-2 file applies a five-second `lock_timeout`. If it times out, abort the release, inspect active transactions and write latency, and retry outside peak traffic; do not increase the timeout while writes are queued.
4. Before the webhook index migration, run the duplicate query below. Quarantine and reconcile any returned IDs without deleting delivery history. The migration repeats this preflight and fails before index construction if duplicates remain.

```sql
select event_id, count(*)
from public.processed_events
group by event_id
having count(*) > 1;
```

Apply `202608280003_processed_events_unique_index.sql` with transaction wrapping disabled. `CREATE UNIQUE INDEX CONCURRENTLY` keeps webhook writes available while PostgreSQL builds the index.

If a concurrent index build fails, inspect validity before retrying:

```sql
select c.relname, i.indisvalid, pg_get_indexdef(i.indexrelid)
from pg_index i
join pg_class c on c.oid = i.indexrelid
where c.relname in ('projects_workspace_id_idx', 'processed_events_event_id_key');
```

An invalid index must be removed with `DROP INDEX CONCURRENTLY <name>` before retrying. If a valid equivalent index exists but migration history is missing, verify its full definition and repair migration history explicitly; never use `IF NOT EXISTS` to accept an unknown or invalid index.

## Database rollback

If request-context propagation fails, stop the rollout before enabling RLS. After enablement, first confirm that restoring the previous unrestricted access model is acceptable, then run `supabase/rollback/202608280003_security.sql` with transaction wrapping disabled. It drops the index concurrently, disables RLS, and removes the dormant policies. Rollback cannot recreate webhook duplicates that operators quarantined during preflight; retain those records until reconciliation is complete.
