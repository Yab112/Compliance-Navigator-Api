"""
Old name for scripts/create_staff.py. Public accounts can no longer be admins; this creates a
staff Super admin instead.

Run from api/:  uv run python -m scripts.create_admin admin@example.gov.et "Full Name"
"""

from scripts.create_staff import main

if __name__ == "__main__":
    main()
