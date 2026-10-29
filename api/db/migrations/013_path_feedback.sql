-- What people tell us when they finish a path: was it accurate, how long did it really take,
-- which steps were different. Differences also become feedback flags for the data team.

create table if not exists path_feedback (
  id uuid primary key default gen_random_uuid(),
  roadmap_id uuid not null references roadmaps (id) on delete cascade,
  user_id uuid references users (id) on delete set null,
  goal text,
  accuracy smallint not null check (accuracy between 1 and 5),
  days_taken integer check (days_taken between 0 and 3650),
  steps_different text[] not null default '{}',
  what_was_different text,
  would_recommend boolean,
  comment text,
  created_at timestamptz not null default now(),
  unique (roadmap_id)
);
create index if not exists path_feedback_goal_idx on path_feedback (goal, created_at desc);
