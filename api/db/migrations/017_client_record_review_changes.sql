-- Both sides are accountable: providers rate clients after a job closes, and a client's
-- review can only change through a request that staff approve.

create table if not exists client_reviews (
  id uuid primary key default gen_random_uuid(),
  engagement_id uuid not null unique references engagements (id) on delete cascade,
  provider_id uuid not null references providers (id) on delete cascade,
  client_user_id uuid not null references users (id) on delete cascade,
  rating int not null check (rating between 1 and 5),
  comment text,
  hidden boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists client_reviews_client_idx on client_reviews (client_user_id, created_at desc);

alter table reviews add column if not exists edited_at timestamptz;

create table if not exists review_change_requests (
  id uuid primary key default gen_random_uuid(),
  review_id uuid not null references reviews (id) on delete cascade,
  requested_by uuid references users (id) on delete set null,
  old_rating int not null,
  old_comment text,
  new_rating int not null check (new_rating between 1 and 5),
  new_comment text,
  reason text not null,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  decided_by text,
  decision_note text,
  decided_at timestamptz,
  created_at timestamptz not null default now()
);
-- One open request per review at a time
create unique index if not exists review_change_one_pending on review_change_requests (review_id) where status = 'pending';
