-- migrate:transaction=false
-- This file must not be wrapped in a transaction: PostgreSQL requires
-- CREATE INDEX CONCURRENTLY to run outside transaction blocks.

do $$
begin
  if exists (
    select event_id
    from public.processed_events
    group by event_id
    having count(*) > 1
  ) then
    raise exception 'processed_events contains duplicate event_id values; quarantine and reconcile duplicates before retrying';
  end if;
end
$$;

-- Do not use IF NOT EXISTS here. A failed concurrent build can leave an
-- identically named INVALID index, and a retry must fail until an operator
-- inspects and drops that invalid artifact.
create unique index concurrently processed_events_event_id_key
on public.processed_events(event_id);
