-- Email verification for public accounts, a shared rate limiter, and one-time keys (webhook replays).

-- When the person proved they read this mailbox. Null = not yet verified: the account works,
-- but they can't become a provider, join or create an organization, or receive payouts.
alter table users add column if not exists email_verified_at timestamptz;

-- Accounts that existed before verification was introduced keep working as before
update users set email_verified_at = coalesce(created_at, now()) where email_verified_at is null;

-- Single-use links, valid 48 hours; only the newest one for a person works
create table if not exists email_verification_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  token_hash text not null unique,
  email text not null,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists email_verification_tokens_user on email_verification_tokens (user_id, created_at desc);

-- Fixed-window counters for core/ratelimit.py: one row per (bucket, key, window)
create table if not exists rate_limit_counters (
  bucket text not null,
  key text not null,
  window_start timestamptz not null,
  hits integer not null default 0,
  primary key (bucket, key, window_start)
);
create index if not exists rate_limit_counters_window on rate_limit_counters (window_start);

-- Keys that may be used once within a time (e.g. a payment webhook body); expired rows are pruned
create table if not exists once_keys (
  bucket text not null,
  key text not null,
  expires_at timestamptz not null,
  primary key (bucket, key)
);
