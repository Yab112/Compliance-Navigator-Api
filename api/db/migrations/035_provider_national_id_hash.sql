-- Providers who joined while Fayda was off typed their national ID number. Keep only a keyed hash
-- (so staff can still find someone by the exact number) and the last four characters (display).
-- scripts/hash_plaintext_national_ids.py moves existing numbers over and clears national_id.

alter table providers add column if not exists national_id_hash text;
alter table providers add column if not exists national_id_last4 text;
create index if not exists providers_national_id_hash_idx on providers (national_id_hash);
