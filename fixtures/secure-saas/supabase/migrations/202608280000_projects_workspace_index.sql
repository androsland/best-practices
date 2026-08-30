-- migrate:transaction=false
-- Build the RLS support index before policies or enforcement are introduced.
-- This file must not be wrapped in a transaction.

create index concurrently projects_workspace_id_idx
on public.projects(workspace_id);
