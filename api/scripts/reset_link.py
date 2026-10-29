"""
Print a one-hour, single-use password reset link for an account (for whoever runs the server).

Run from api/:  uv run python -m scripts.reset_link someone@example.com
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import service
from services import user_store
from services.db import run_migrations


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    run_migrations()
    user = user_store.get_user_by_email(sys.argv[1])
    if not user:
        sys.exit("No account with that email")
    print(service.create_reset_link(user, created_by="cli"))
    service.record_event("reset_link_issued", user_id=user["id"], detail="by server CLI")


if __name__ == "__main__":
    main()
