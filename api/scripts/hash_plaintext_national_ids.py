"""
One-time cleanup: stop storing national ID numbers in providers.national_id.

Providers who joined while Fayda was off have the full number they typed there. This moves each
value to national_id_hash (the same keyed hash as Fayda verification) and national_id_last4, then
clears national_id. Rows that already hold a masked value ("FIN •••• 1234", from Fayda) keep the
last four, take the hash from their verified Fayda record, and are cleared too.

Needs ID_HASH_PEPPER set to the production value first: hashes made with another pepper never match.

Run from api/:
  .venv/bin/python -m scripts.hash_plaintext_national_ids            # dry run: counts only
  .venv/bin/python -m scripts.hash_plaintext_national_ids --apply    # make the change
Never prints ID numbers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import settings
from services import id_verification
from services.db import connection, fetch_all, fetch_one, run_migrations

MASK = "•"


def _plan() -> list[dict]:
    rows = fetch_all(
        """
        select p.id::text, p.national_id, v.id_hash as verified_hash
        from providers p
        left join id_verifications v on v.user_id = p.user_id and v.status = 'verified'
        where p.national_id is not null
        """
    )
    plan = []
    for row in rows:
        value = row["national_id"].strip()
        if MASK in value:
            # Already masked: only the last four are known; the hash comes from the Fayda record
            last4 = id_verification.normalize_id(value.split(MASK)[-1])[-4:] or None
            plan.append({"id": row["id"], "kind": "masked", "hash": row["verified_hash"], "last4": last4})
        else:
            id_hash, last4 = id_verification.id_hash_and_last4(value)
            plan.append({"id": row["id"], "kind": "plaintext", "hash": id_hash, "last4": last4})
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the hashes and clear national_id")
    args = parser.parse_args()

    if args.apply:
        run_migrations()
    elif not fetch_one(
        "select 1 from information_schema.columns where table_name = 'providers' and column_name = 'national_id_hash'"
    ):
        print("Note: migration 035 (national_id_hash, national_id_last4) is not applied yet; --apply applies it.")

    if not settings.id_hash_pepper:
        print("Warning: ID_HASH_PEPPER is not set, hashes would use SECRET_KEY. Set it before --apply in production.")

    plan = _plan()
    plaintext = sum(1 for p in plan if p["kind"] == "plaintext")
    masked = len(plan) - plaintext
    no_hash = sum(1 for p in plan if not p["hash"])
    print(f"Providers with a value in national_id: {len(plan)}")
    print(f"  full numbers (plaintext) to hash: {plaintext}")
    print(f"  already masked, last four kept: {masked}")
    print(f"  rows left without a hash (masked with no verified Fayda record): {no_hash}")

    if not args.apply:
        print("Dry run, nothing changed. Run with --apply to make the change.")
        return

    with connection() as conn, conn.transaction():
        for p in plan:
            conn.execute(
                """
                update providers set national_id_hash = coalesce(%s, national_id_hash),
                  national_id_last4 = coalesce(%s, national_id_last4), national_id = null, updated_at = now()
                where id = %s
                """,
                (p["hash"], p["last4"], p["id"]),
            )
        left = conn.execute("select count(*) as c from providers where national_id is not null").fetchone()["c"]
    print(f"Done: {len(plan)} rows updated, {left} still have national_id set.")


if __name__ == "__main__":
    main()
