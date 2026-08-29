-- migrate:transaction=false
-- Use only after confirming the previous unrestricted access model is safe.

drop index concurrently if exists public.processed_events_event_id_key;

alter table public.projects disable row level security;

drop policy if exists "workspace members delete projects" on public.projects;
drop policy if exists "workspace members update projects" on public.projects;
drop policy if exists "workspace members create projects" on public.projects;
drop policy if exists "workspace members read projects" on public.projects;
