-- Phase 1: deploy request-context propagation before enabling RLS. These
-- policies are dormant until 202608280002_enable_projects_rls.sql runs.

create policy "workspace members read projects"
on public.projects for select
using (workspace_id = current_setting('app.workspace_id', true)::uuid);

create policy "workspace members create projects"
on public.projects for insert
with check (workspace_id = current_setting('app.workspace_id', true)::uuid);

create policy "workspace members update projects"
on public.projects for update
using (workspace_id = current_setting('app.workspace_id', true)::uuid)
with check (workspace_id = current_setting('app.workspace_id', true)::uuid);

create policy "workspace members delete projects"
on public.projects for delete
using (workspace_id = current_setting('app.workspace_id', true)::uuid);
