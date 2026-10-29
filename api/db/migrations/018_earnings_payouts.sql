-- Clients pay the platform after delivery; each paid job credits the provider's earnings balance;
-- providers withdraw through payout requests that staff approve, paid to their own bank account.

alter table engagements add column if not exists payment_requested_at timestamptz;

-- The full account number is needed to send payouts; stored encrypted, shown only as the last 4 digits
alter table providers add column if not exists payout_account_enc text;

-- Every movement of a provider's money: + earnings, - payouts. The balance is the sum.
create table if not exists provider_ledger (
  id bigserial primary key,
  provider_id uuid not null references providers (id) on delete cascade,
  kind text not null check (kind in ('earning', 'payout', 'adjustment')),
  amount numeric(12, 2) not null,
  engagement_id uuid references engagements (id) on delete set null,
  payment_id uuid references payments (id) on delete set null,
  payout_id uuid,
  note text,
  created_at timestamptz not null default now()
);
create index if not exists provider_ledger_provider_idx on provider_ledger (provider_id, created_at desc);
-- One earning per payment, so a payment confirmed twice never pays twice
create unique index if not exists provider_ledger_one_earning on provider_ledger (payment_id) where kind = 'earning';

create table if not exists payouts (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references providers (id) on delete cascade,
  amount numeric(12, 2) not null check (amount > 0),
  status text not null default 'requested'
    check (status in ('requested', 'approved', 'paid', 'rejected', 'failed')),
  bank_code text not null,
  bank_name text,
  account_name text not null,
  account_last4 text not null,
  reference text not null unique,
  gateway text,
  gateway_reference text,
  note text,
  decided_by text,
  decided_at timestamptz,
  paid_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists payouts_status_idx on payouts (status, created_at);
create index if not exists payouts_provider_idx on payouts (provider_id, created_at desc);

-- Split payments (Chapa subaccounts) are no longer used: money comes to us and is paid out on request
alter table providers drop column if exists payout_subaccount_id;
