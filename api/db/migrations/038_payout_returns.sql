-- A bank transfer Chapa first reported as paid can bounce later (wrong account, closed account, reversed).
-- The money then sits in our Chapa account again. Staff record it as returned, a second staff member
-- approves, and the provider gets the amount back in their balance as one 'payout_return' ledger line.

alter table payouts drop constraint if exists payouts_status_check;
alter table payouts add constraint payouts_status_check
  check (status in ('requested', 'approved', 'paid', 'rejected', 'failed', 'returned'));

alter table payouts
  add column if not exists returned_at timestamptz,
  add column if not exists returned_by text,
  add column if not exists return_note text;

alter table provider_ledger drop constraint if exists provider_ledger_kind_check;
alter table provider_ledger add constraint provider_ledger_kind_check
  check (kind in ('earning', 'payout', 'adjustment', 'refund', 'payout_return'));

-- A returned payout is credited back once, whatever happens
create unique index if not exists provider_ledger_one_payout_return
  on provider_ledger (payout_id) where kind = 'payout_return';

-- The daily check asks Chapa again about recent paid transfers
create index if not exists payouts_paid_at_idx on payouts (paid_at) where status = 'paid';
