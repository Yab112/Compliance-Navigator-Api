-- Cut the admin app loose from public accounts.
-- Every public account with the admin role becomes a staff member (same id, same password hash,
-- so a password set directly in the database keeps working) and a Super admin. The public
-- account stays an ordinary account: nothing on the public site grants admin power any more.

insert into staff_users (id, email, fullname, password_hash, status, password_changed_at, last_login_at, created_by, created_at)
select u.id, lower(u.email), coalesce(u.fullname, ''), u.password_hash,
       case when u.is_active then 'active' else 'disabled' end,
       u.password_changed_at, u.last_login_at, 'migration 026', u.created_at
from users u
where u.role = 'admin'
on conflict do nothing;

insert into staff_user_roles (staff_id, role_id, granted_by)
select s.id, r.id, 'migration 026'
from staff_users s join users u on u.id = s.id and u.role = 'admin'
cross join staff_roles r where r.builtin_key = 'super_admin'
on conflict do nothing;

update users set role = 'user', updated_at = now() where role = 'admin';

alter table users drop constraint if exists users_role_check;
alter table users add constraint users_role_check check (role in ('user', 'agent'));

-- Support tickets are assigned to staff, and staff replies are written by staff
alter table support_tickets drop constraint if exists support_tickets_assignee_id_fkey;
update support_tickets set assignee_id = null
where assignee_id is not null and assignee_id not in (select id from staff_users);
alter table support_tickets add constraint support_tickets_assignee_id_fkey
  foreign key (assignee_id) references staff_users (id) on delete set null;

-- author_id points at users for customer messages and at staff_users for staff ones
alter table support_messages drop constraint if exists support_messages_author_id_fkey;
