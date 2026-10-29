-- Payments made before earnings existed: credit each provider's share once
insert into provider_ledger (provider_id, kind, amount, engagement_id, payment_id, note, created_at)
select e.provider_id, 'earning', p.provider_amount, p.engagement_id, p.id,
       p.commission_percent::text || '% platform commission deducted', coalesce(p.verified_at, p.updated_at)
from payments p join engagements e on e.id = p.engagement_id
where p.status = 'success' and e.provider_id is not null
on conflict do nothing;
