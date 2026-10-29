"""
Let a sample provider sign in, to try the marketplace from the provider's side.

Run from api/:  uv run python -m scripts.demo_login meron [abay ...]

Sample accounts use @sample.invalid addresses so they normally can't sign in. This gives the
named ones a <name>.sample@example.com address and the demo password stored as
DEMO_PASSWORD in api/.env (generated on first use; .env is never committed). purge_samples()
still removes them. Never run this on a production database.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.security import hash_password  # noqa: E402
from services.db import execute, fetch_one  # noqa: E402

ENV = Path(__file__).resolve().parent.parent / ".env"


def demo_password() -> str:
    for line in ENV.read_text().splitlines() if ENV.exists() else []:
        if line.startswith("DEMO_PASSWORD="):
            return line.split("=", 1)[1].strip()
    password = "Demo" + secrets.token_urlsafe(9) + "7"
    with ENV.open("a") as f:
        f.write(f"\n# Sign-in password for sample accounts enabled with scripts.demo_login\nDEMO_PASSWORD={password}\n")
    return password


def main() -> None:
    if os.environ.get("ENVIRONMENT") == "production":
        sys.exit("Refusing to create demo logins in production")
    names = [n.lower() for n in sys.argv[1:]]
    if not names:
        sys.exit(__doc__)
    hashed = hash_password(demo_password())
    for name in names:
        row = fetch_one(
            "select u.id::text, p.display_name from providers p join users u on u.id = p.user_id "
            "where p.is_sample and (u.email = %s or u.email = %s)",
            (f"sample-{name}@sample.invalid", f"{name}.sample@example.com"),
        )
        if not row:
            print(f"  no sample provider called {name!r}")
            continue
        email = f"{name}.sample@example.com"
        execute("update users set email = %s, password_hash = %s, is_active = true where id = %s", (email, hashed, row["id"]))
        print(f"  {row['display_name']}: sign in as {email}")
    print(f"Password: DEMO_PASSWORD in {ENV}")


if __name__ == "__main__":
    main()
