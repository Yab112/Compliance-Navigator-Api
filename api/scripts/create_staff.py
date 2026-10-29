"""
Create a staff Super admin for the admin app (the bootstrap for a fresh install).

Run from api/:  uv run python -m scripts.create_staff admin@example.gov.et "Full Name"
Prompts for the password. Staff accounts are separate from public accounts; after this, invite
everyone else from Access, Staff in the admin app.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.security import hash_password, password_problem
from auth.staff_service import audit, get_staff_by_email
from services.db import fetch_one, run_migrations


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    email, fullname = sys.argv[1].strip().lower(), (sys.argv[2] if len(sys.argv) > 2 else "")
    run_migrations()
    if get_staff_by_email(email):
        sys.exit(f"{email} is already on staff. Use the admin app (Access, Staff) to change their roles.")
    password = getpass.getpass("Password (min 8 chars, a letter and a number): ")
    problem = password_problem(password)
    if problem:
        sys.exit(problem)
    staff = fetch_one(
        "insert into staff_users (email, fullname, password_hash, status, created_by, password_changed_at) "
        "values (%s, %s, %s, 'active', 'scripts.create_staff', now()) returning id::text",
        (email, fullname, hash_password(password)),
    )
    fetch_one(
        "insert into staff_user_roles (staff_id, role_id, granted_by) "
        "select %s, id, 'scripts.create_staff' from staff_roles where builtin_key = 'super_admin' returning staff_id",
        (staff["id"],),
    )
    audit("staff.created_from_shell", actor_email=email, target=f"staff:{staff['id']}", details={"role": "Super admin"})
    print(f"{email} is now a staff Super admin. Sign in at the admin app.")


if __name__ == "__main__":
    main()
