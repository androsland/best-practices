-- Phase 2: apply only after every live application version sets
-- app.workspace_id and role-level integration tests pass.

alter table public.projects enable row level security;
