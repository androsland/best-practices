alter table public.projects enable row level security;

create policy "workspace members read projects"
on public.projects for select
using (workspace_id = current_setting('app.workspace_id')::uuid);

create unique index processed_events_event_id_key on public.processed_events(event_id);
