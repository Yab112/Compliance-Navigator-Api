-- Reminders people asked for ("remind me before my licence renewal"), created only after they confirm.
-- Delivered to the notification bell on their due date: when the person's bell loads, and by the daily
-- job where a worker runs.

create table if not exists user_reminders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  title text not null check (length(title) between 3 and 200),
  body text check (body is null or length(body) <= 1000),
  due_on date not null,
  link text check (link is null or link like '/%'),   -- a page on our own site only
  source text not null default 'assistant' check (source in ('assistant', 'path', 'account')),
  conversation_id uuid,
  created_at timestamptz not null default now(),
  delivered_at timestamptz,
  cancelled_at timestamptz
);

create index if not exists user_reminders_due_idx on user_reminders (due_on)
  where delivered_at is null and cancelled_at is null;
create index if not exists user_reminders_user_idx on user_reminders (user_id, due_on);
