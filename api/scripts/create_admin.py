"""
Create or promote an admin account.

Run from api/:  uv run python -m scripts.create_admin admin@example.gov.et "Full Name"
Prompts for a password when the account doesn't exist yet.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.security import hash_password, password_problem
from services import user_store
from services.db import execute, run_migrations


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    email, fullname = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    run_migrations()

    user = user_store.get_user_by_email(email)
    if not user:
        password = getpass.getpass("Password (min 8 chars): ")
        problem = password_problem(password)
        if problem:
            sys.exit(problem)
        user = user_store.create_user(email, fullname, hash_password(password))
    execute("update users set role = 'admin', is_active = true where id = %s", (user["id"],))
    print(f"{email} is now an admin.")


if __name__ == "__main__":
    main()
