-- Every HTTP call to a payment gateway (Chapa), so staff can see whether it is answering and what went wrong.
-- No secret key, no account numbers and no personal data: only the operation, a path template and our reference.
-- Rows older than 90 days are removed by the daily maintenance (services/payment_service/health.py).

create table if not exists gateway_calls (
  id bigserial primary key,
  gateway text not null,
  operation text not null
    check (operation in ('initialize', 'verify', 'transfer', 'verify_transfer', 'refund', 'verify_refund', 'banks', 'other')),
  method text not null,
  path text not null,               -- a template such as /transaction/verify/{ref}; the reference is stored below
  reference text,                   -- tx_ref, payout reference or refund reference, when known
  http_status int,                  -- null when Chapa never answered (timeout, connection error)
  ok boolean not null,
  uncertain boolean not null default false,  -- the call may have been carried out anyway
  error text,                       -- what Chapa said (or the network error), at most 500 characters
  duration_ms int not null default 0,
  is_test boolean not null default false,    -- made with a Chapa test key
  created_at timestamptz not null default now()
);

create index if not exists gateway_calls_created_idx on gateway_calls (created_at desc);
create index if not exists gateway_calls_ok_created_idx on gateway_calls (ok, created_at desc);
-- The latest error for a payment, payout or refund reference
create index if not exists gateway_calls_reference_idx on gateway_calls (reference, created_at desc) where reference is not null;
