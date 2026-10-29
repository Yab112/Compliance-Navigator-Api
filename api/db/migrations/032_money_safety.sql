-- Money safety: payouts go to the account they were asked for, test money never becomes withdrawable
-- once payments are live, a second payment for the same job is never credited, and refunds.

-- A payout keeps the exact account it was requested with (encrypted). Approval sends to this account,
-- never to whatever is on the provider's profile at that moment.
alter table payouts
  add column if not exists account_enc text,
  -- made while payments were in test mode (simulated, or Chapa with a test key): never sent for real
  add column if not exists is_test boolean not null default false,
  -- the transfer call failed in a way that does not prove the money stayed: check with Chapa first
  add column if not exists needs_check boolean not null default false,
  add column if not exists check_note text;

-- Waiting payouts from before this change: keep the account on file only when it is the same one
update payouts po set account_enc = p.payout_account_enc
from providers p
where po.provider_id = p.id and po.account_enc is null and po.status in ('requested', 'approved')
  and p.payout_account_enc is not null and p.payout_account_last4 = po.account_last4
  and p.payout_bank_code = po.bank_code and p.payout_set_at <= po.created_at;

alter table payments
  add column if not exists is_test boolean not null default false,
  -- money received but not credited to anyone: 'duplicate' (the job was already paid) or 'job_closed'
  add column if not exists unapplied_reason text check (unapplied_reason in ('duplicate', 'job_closed')),
  -- running totals of what was refunded; the original figures stay as they were for the receipt
  add column if not exists refunded_amount numeric(12, 2) not null default 0,
  add column if not exists refunded_commission numeric(12, 2) not null default 0,
  add column if not exists refunded_commission_vat numeric(12, 2) not null default 0,
  add column if not exists refunded_provider_amount numeric(12, 2) not null default 0,
  add column if not exists refunded_provider_vat numeric(12, 2) not null default 0;

-- Chapa says on each verified payment whether it ran with a test key
update payments set is_test = true
where not is_test and (gateway = 'simulated' or raw -> 'verify' ->> 'mode' = 'test');

alter table provider_ledger add column if not exists is_test boolean not null default false;
alter table provider_ledger add column if not exists refund_id uuid;
alter table provider_ledger drop constraint if exists provider_ledger_kind_check;
alter table provider_ledger add constraint provider_ledger_kind_check
  check (kind in ('earning', 'payout', 'adjustment', 'refund'));

update provider_ledger l set is_test = true
from payments p where l.payment_id = p.id and p.is_test and not l.is_test;

-- A waiting payout is test money when the provider has no real earnings to cover it
update payouts po set is_test = true
where not po.is_test and (po.gateway = 'simulated' or po.status in ('requested', 'approved') and po.amount > coalesce(
  (select sum(l.amount) from provider_ledger l where l.provider_id = po.provider_id and not l.is_test), 0));
update provider_ledger l set is_test = true
from payouts po where l.payout_id = po.id and po.is_test and not l.is_test;

-- Refunds to clients, always approved by a second staff member
create table if not exists refunds (
  id uuid primary key default gen_random_uuid(),
  payment_id uuid not null references payments (id) on delete cascade,
  engagement_id uuid references engagements (id) on delete set null,
  reference text not null unique,
  amount numeric(12, 2) not null check (amount > 0),        -- what the client gets back
  -- how the amount splits, taken back from each side in proportion to the original payment
  price_part numeric(12, 2) not null default 0,
  provider_vat numeric(12, 2) not null default 0,
  commission numeric(12, 2) not null default 0,
  commission_vat numeric(12, 2) not null default 0,
  provider_amount numeric(12, 2) not null default 0,          -- taken back from the provider's earnings
  reason text not null,
  method text not null check (method in ('gateway', 'manual')),
  status text not null default 'sending'
    check (status in ('sending', 'processing', 'refunded', 'manual_pending', 'needs_check', 'failed')),
  applied boolean not null default false,                     -- the figures above are counted on the payment
  gateway text,
  gateway_ref text,
  is_test boolean not null default false,
  -- manual refunds: where the client asked to be paid back
  client_bank_name text,
  client_account_name text,
  client_account_enc text,
  client_account_last4 text,
  transfer_reference text,
  requested_by text,
  approved_by text,
  confirmed_by text,
  error text,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);
create index if not exists refunds_payment_idx on refunds (payment_id, created_at desc);
create index if not exists refunds_status_idx on refunds (status, created_at desc);
create unique index if not exists provider_ledger_one_refund on provider_ledger (refund_id) where kind = 'refund';
