-- Phase 2 is deliberately outside supabase/migrations so a normal migration
-- push cannot cross the mixed-version deployment boundary automatically.
-- Apply only after every live application version sets app.workspace_id and
-- the role-level integration checks pass.

set lock_timeout = '5s';
alter table public.projects enable row level security;
reset lock_timeout;
