# Deployment and rollback

Terraform and the release workflow deploy immutable images. Rollback selects the previous image revision and pauses if a data migration is not backward compatible.

## Security migration rollout

1. Deploy application code that sets `app.workspace_id` for every project read and write. Verify anonymous, cross-workspace, same-workspace, and background-worker behavior while RLS remains disabled.
2. Apply `202608280001_workspace_policies.sql`. The policies remain dormant during the mixed-version window.
3. Drain every application version that does not set the request context, then apply `202608280002_enable_projects_rls.sql` and repeat the role-level integration checks.
4. Before the webhook index migration, run the duplicate query below. Quarantine and reconcile any returned IDs without deleting delivery history. The migration repeats this preflight and fails before index construction if duplicates remain.

```sql
select event_id, count(*)
from public.processed_events
group by event_id
having count(*) > 1;
```

Apply `202608280003_processed_events_unique_index.sql` with transaction wrapping disabled. `CREATE UNIQUE INDEX CONCURRENTLY` keeps webhook writes available while PostgreSQL builds the index.

## Database rollback

If request-context propagation fails, stop the rollout before enabling RLS. After enablement, first confirm that restoring the previous unrestricted access model is acceptable, then run `supabase/rollback/202608280003_security.sql` with transaction wrapping disabled. It drops the index concurrently, disables RLS, and removes the dormant policies. Rollback cannot recreate webhook duplicates that operators quarantined during preflight; retain those records until reconciliation is complete.
