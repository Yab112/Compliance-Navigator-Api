-- Client and provider talk on Telegram after the provider accepts; the in-app chat is retired.

drop table if exists hire_messages;

-- Telegram usernames (without the @), shared with the other side only once a job is accepted
alter table users add column if not exists telegram_username text;
alter table providers add column if not exists telegram_username text;
alter table engagements add column if not exists client_telegram text;
