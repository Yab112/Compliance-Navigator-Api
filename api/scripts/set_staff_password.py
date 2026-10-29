"""
Set a new password for an existing staff member from the shell, and optionally make them a Super admin.

Run from api/:
  uv run python -m scripts.set_staff_password someone@example.gov.et
      prompts for the new password (it can also be piped in)
  uv run python -m scripts.set_staff_password someone@example.gov.et --generate ~/staff-login.txt
      makes a strong random password and writes the email and password to that file (owner-only,
      outside the repo); nothing is printed
  add --super-admin to also give them the Super admin role if they don't hold it

The account becomes active, every session and open invite or reset link is ended, and the change
goes into the staff audit log. For day-to-day resets use "Send reset link" in Access, Staff instead.
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.security import hash_password, password_problem
from auth.staff_service import (
    audit,
    get_staff_by_email,
    revoke_all_sessions,
    revoke_links,
)
from services.db import connection, run_migrations

REPO_ROOT = Path(__file__).resolve().parents[2]


def _generated_password() -> str:
    # 20 url-safe characters plus a guaranteed letter and digit for the password rules
    return secrets.token_urlsafe(15) + secrets.choice("abcdefghjkmnpqrstuvwxyz") + secrets.choice("23456789")


def _check_secret_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        sys.exit(f"Refusing to write a password inside the repository ({REPO_ROOT}). Pick a path outside it.")
    return path


def _write_secret(path: Path, email: str, password: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"Admin app staff sign-in\nemail: {email}\npassword: {password}\n")
    os.chmod(path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--generate", metavar="FILE", type=Path, help="make a random password and save it to FILE")
    parser.add_argument("--super-admin", action="store_true", help="also grant the Super admin role")
    args = parser.parse_args()

    email = args.email.strip().lower()
    run_migrations()
    staff = get_staff_by_email(email)
    if not staff:
        sys.exit(f"{email} is not on staff. Create them with scripts.create_staff or invite them in the admin app.")

    if args.generate:
        # Checked before anything changes, so a bad path never leaves an unknown password behind
        args.generate = _check_secret_path(args.generate)
        password = _generated_password()
    else:
        try:
            password = getpass.getpass("New password (min 8 chars, a letter and a number): ")
        except EOFError:
            sys.exit("No password was typed (this shell has no keyboard input). Run it in a normal terminal, "
                     "or use --generate FILE.")
    problem = password_problem(password)
    if problem:
        sys.exit(problem)

    granted = False
    with connection() as conn, conn.transaction():
        conn.execute(
            "update staff_users set password_hash = %s, password_changed_at = now(), must_change_password = false, "
            "status = 'active', updated_at = now() where id = %s",
            (hash_password(password), staff["id"]),
        )
        if args.super_admin:
            granted = bool(
                conn.execute(
                    "insert into staff_user_roles (staff_id, role_id, granted_by) "
                    "select %s, id, 'scripts.set_staff_password' from staff_roles where builtin_key = 'super_admin' "
                    "on conflict do nothing returning staff_id",
                    (staff["id"],),
                ).fetchone()
            )
    ended = revoke_all_sessions(staff["id"], "password set from shell")
    revoke_links(staff["id"])
    audit(
        "staff.password_set_from_shell",
        actor_email=email,
        target=f"staff:{staff['id']}",
        details={"sessions_ended": ended, "super_admin_granted": granted},
    )
    if args.generate:
        _write_secret(args.generate, email, password)
        print(f"New password for {email} saved to {args.generate} (only you can read it).")
    else:
        print(f"New password set for {email}.")
    if args.super_admin:
        print("Super admin role granted." if granted else "Already a Super admin.")
    print(f"Signed out of {ended} session(s). Sign in at the admin app with the new password.")


if __name__ == "__main__":
    main()
