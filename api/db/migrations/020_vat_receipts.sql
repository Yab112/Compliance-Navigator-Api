-- VAT (Proclamation 1341/2024, standard rate 15%) and receipts.
--  * Our commission is our service: VAT is charged on it and deducted with it from the provider's share.
--  * A VAT-registered provider charges VAT on their own service: the client pays price + VAT, and that
--    VAT goes to the provider, who files it.
-- Amounts are frozen on the payment at the moment it is created, so a receipt never changes later.

alter table providers
  add column if not exists vat_registered boolean not null default false,
  add column if not exists vat_number text;

alter table payments
  add column if not exists price numeric(12, 2),            -- the provider's agreed price, before VAT
  add column if not exists vat_rate numeric(5, 2) not null default 0,
  add column if not exists provider_vat numeric(12, 2) not null default 0,   -- VAT the provider charges the client
  add column if not exists commission_vat numeric(12, 2) not null default 0, -- VAT on our commission
  add column if not exists provider_vat_number text;

-- Payments made before this: the amount was the price, no VAT was charged
update payments set price = amount where price is null;
