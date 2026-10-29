-- Property and car brokers (delala) are out of scope: the marketplace is for getting things done
-- with offices. Sample brokers and their sample jobs are removed; a real broker profile, if any,
-- is suspended (never silently deleted) and the type stays allowed until staff resolve it.

delete from engagements
where provider_id in (select id from providers where provider_type = 'delala' and is_sample);

with gone as (
  delete from providers where provider_type = 'delala' and is_sample returning user_id
)
delete from users where id in (select user_id from gone) and email like '%@sample.invalid';

update providers set status = 'suspended', accepting_work = false
where provider_type = 'delala' and status <> 'suspended';

update providers set specialties = array_remove(specialties, 'real_estate')
where 'real_estate' = any(specialties);

do $$
begin
  if not exists (select 1 from providers where provider_type = 'delala') then
    alter table providers drop constraint if exists providers_provider_type_check;
    alter table providers add constraint providers_provider_type_check
      check (provider_type in ('guday_geday', 'agency'));
  end if;
end $$;
