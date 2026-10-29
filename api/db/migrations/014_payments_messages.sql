-- Paying providers through the platform (Chapa split payments) and messages inside each hire.

-- Where a provider is paid. Only the last four digits of the account number are kept.
alter table providers
  add column if not exists payout_subaccount_id text,
  add column if not exists payout_bank_code text,
  add column if not exists payout_bank_name text,
  add column if not exists payout_account_name text,
  add column if not exists payout_account_last4 text,
  add column if not exists payout_set_at timestamptz;

-- The price the provider names when accepting, and whether it was paid through us
alter table engagements
  add column if not exists agreed_price numeric(12, 2) check (agreed_price is null or agreed_price > 0),
  add column if not exists price_note text,
  add column if not exists payment_status text not null default 'unpaid'
    check (payment_status in ('unpaid', 'pending', 'paid', 'failed', 'refunded')),
  add column if not exists paid_at timestamptz;

create table if not exists payments (
  id uuid primary key default gen_random_uuid(),
  engagement_id uuid not null references engagements (id) on delete cascade,
  payer_user_id uuid references users (id) on delete set null,
  tx_ref text not null unique,
  gateway text not null check (gateway in ('chapa', 'simulated')),
  amount numeric(12, 2) not null check (amount > 0),
  currency text not null default 'ETB',
  commission_percent numeric(5, 2) not null,
  commission_amount numeric(12, 2) not null,
  provider_amount numeric(12, 2) not null,
  subaccount_id text,
  status text not null default 'pending' check (status in ('pending', 'success', 'failed', 'cancelled')),
  checkout_url text,
  gateway_reference text,
  payment_method text,
  gateway_fee numeric(12, 2),
  raw jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  verified_at timestamptz
);
create index if not exists payments_engagement_idx on payments (engagement_id, created_at desc);
create index if not exists payments_status_idx on payments (status, created_at desc);

create table if not exists hire_messages (
  id bigserial primary key,
  engagement_id uuid not null references engagements (id) on delete cascade,
  sender_user_id uuid references users (id) on delete set null,
  sender_role text not null check (sender_role in ('client', 'provider', 'system')),
  body text not null,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists hire_messages_engagement_idx on hire_messages (engagement_id, id);
