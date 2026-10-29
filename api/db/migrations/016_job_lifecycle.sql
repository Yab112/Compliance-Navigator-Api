-- A hire moves in clear steps: requested -> accepted (price) -> paid -> in progress ->
-- delivered (provider's note) -> closed (client confirms, or automatically after 7 days) -> reviewed.
-- Job Success is worked out from closed jobs only.

alter table engagements
  add column if not exists completion_note text,         -- what the provider says they delivered
  add column if not exists auto_confirmed boolean not null default false;

alter table providers
  add column if not exists job_success integer check (job_success between 0 and 100),  -- null until 3 closed jobs
  add column if not exists closed_jobs integer not null default 0;

-- Jobs completed before confirmation existed: past the 7-day window they count as closed
update engagements set client_confirmed_at = coalesce(completed_at, updated_at), auto_confirmed = true
where status = 'completed' and client_confirmed_at is null and not coalesce(disputed, false)
  and coalesce(completed_at, updated_at) < now() - interval '7 days';
