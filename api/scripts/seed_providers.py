"""
Seed SAMPLE marketplace data so the directory, profiles and scores aren't empty in demos.

Run from api/:  uv run python -m scripts.seed_providers
Remove with:    uv run python -m scripts.seed_providers --purge   (or Admin > Marketplace)
Make the existing sample providers ready to work again (after new rules or a new legal version):
                uv run python -m scripts.seed_providers --make-ready

Every name here is fictional. Rows are flagged is_sample and the accounts use
@sample.invalid emails, so they can't sign in and are easy to purge.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import provider_service as svc, user_store  # noqa: E402
from services.db import execute, fetch_one, run_migrations  # noqa: E402

random.seed(42)

PROVIDERS = [
    # Guday Geday individuals
    dict(key="meron", provider_type="guday_geday", entity_type="individual", display_name="Meron Tadesse",
         display_name_am="ሜሮን ታደሰ", headline="Passports and Fayda ID, done right the first time",
         bio="Six years helping families with passport renewals, damaged passport corrections and Fayda "
             "registration. I check every document before we go so you are never sent back.",
         service_areas=["bole", "yeka", "kirkos"], service_ids=["mesob-728", "mesob-730", "mesob-811"],
         languages=["am", "en"], experience_years=6, fee_from=800, fee_to=1500, fee_unit="per_job",
         highlights=["120+ passport files handled", "Knows ICS Bole branch queues"], tin="0011223344",
         months=18, reviews=[5, 5, 4, 5, 5, 4, 5], declined=0),
    dict(key="dawit", provider_type="guday_geday", entity_type="individual", display_name="Dawit Bekele",
         display_name_am="ዳዊት በቀለ", headline="Trade licence, TIN and commercial registration for small businesses",
         bio="I take new shops and service businesses from TIN to trade licence. I prepare the forms, "
             "book the MESOB visits and keep you updated on Telegram.",
         service_areas=["arada", "addis_ketema", "lideta"], service_ids=["mesob-802", "mesob-805", "mesob-792"],
         languages=["am", "om"], experience_years=4, fee_from=1500, fee_to=4000, fee_unit="per_job",
         months=9, reviews=[4, 5, 3, 4], declined=1),
    dict(key="hiwot", provider_type="guday_geday", entity_type="individual", display_name="Hiwot Girma",
         display_name_am="ሕይወት ግርማ", headline="Document authentication at DARS and MoFA",
         bio="Lease agreements, declarations and documents for use abroad, authenticated without the back and forth.",
         service_areas=["kirkos", "nifas_silk"], service_ids=["mesob-862", "mesob-868", "mesob-753"],
         languages=["am", "en"], experience_years=2, fee_from=600, fee_to=1200, fee_unit="per_job",
         months=3, reviews=[5], declined=0),
    # Agencies (companies)
    dict(key="abay", provider_type="agency", entity_type="company", display_name="Abay Clearing & Forwarding",
         legal_name="Abay Clearing and Forwarding PLC", headline="Customs clearing at Modjo dry port and Bole cargo",
         bio="Licensed clearing agent for importers and diaspora shipments. We handle declarations, duty "
             "calculation and port follow-up so goods are released on time.",
         specialties=["customs_clearing"], service_areas=["nationwide", "adama"], languages=["am", "en"],
         experience_years=14, fee_from=3000, fee_to=15000, fee_unit="per_job", tin="0055667788",
         trade_license_no="AA/BL/14/06789", external_license_type="Customs clearing agent permit",
         external_license_no="ECC-CA-1182", license_verified=True, representative_title="Operations manager",
         months=22, reviews=[5, 4, 4, 5, 5], declined=0),
    dict(key="selam_travel", provider_type="agency", entity_type="company", display_name="Selam Visa & Travel",
         legal_name="Selam Travel and Tour PLC", headline="Visa applications, flights and travel documents",
         bio="Visa application support for Schengen, UAE and US, plus passport and yellow card checks before you apply.",
         specialties=["travel_visa"], service_areas=["bole", "kirkos"], languages=["am", "en", "ti"],
         experience_years=7, fee_from=2500, fee_to=6000, fee_unit="per_job", tin="0099887766",
         trade_license_no="AA/BL/12/04411", external_license_type="Travel agency licence (Ministry of Tourism)",
         external_license_no="MOT-TA-2231", license_verified=False, months=7, reviews=[4, 5, 4], declined=1),
    # Clearing agency staff (individual Guday Geday who join Abay)
    dict(key="biruk", provider_type="guday_geday", entity_type="individual", display_name="Biruk Haile",
         headline="Clearing documents and MoTRI follow-up for importers",
         bio="Member of Abay Clearing. I prepare import permits and follow files at the trade ministry.",
         service_areas=["bole", "nationwide"], service_ids=["mesob-753", "mesob-802"], languages=["am", "en"],
         experience_years=3, fee_from=1000, fee_to=2500, fee_unit="per_job", months=10, reviews=[5, 4, 5], declined=0,
         member_of="abay"),
    dict(key="saba", provider_type="guday_geday", entity_type="individual", display_name="Saba Woldemariam",
         headline="Commercial registration and licence renewals",
         service_areas=["bole", "kirkos"], service_ids=["mesob-792", "mesob-805"], languages=["am"],
         experience_years=2, months=4, reviews=[4, 5], declined=1, member_of="abay"),
]

COMMENTS = {
    5: ["Finished faster than promised and explained every step.", "Honest about the fee from the start. Highly recommend.",
        "Everything was ready on the first visit. No running around."],
    4: ["Good work, one extra trip but they warned me in advance.", "Reliable and polite. Slightly slow to reply."],
    3: ["Got it done, but communication could be better."],
    2: ["Asked for more money halfway through. Job was done in the end."],
}
# Job titles per agency specialty, or per first service for Guday Geday agents
JOBS = {
    "customs_clearing": ["Clear an imported vehicle at Modjo", "Clear a cargo shipment at Bole", "Clear medical equipment"],
    "travel_visa": ["Schengen visa application", "UAE work visa documents", "US visa interview preparation"],
    "guday_geday": ["Renew my passport", "Get my trade licence", "Authenticate a lease agreement", "Register a new TIN"],
}


def _jobs_for(p: dict) -> list[str]:
    titles = [t for s in p["specialties"] for t in JOBS.get(s, [])]
    return titles or JOBS["guday_geday"]


def _user(email: str, name: str) -> dict:
    return user_store.get_user_by_email(email) or user_store.create_user(email, name, None)


SAMPLE_FILE = "sample/none"  # sample documents have no file behind them


def make_ready(provider_id: str) -> None:
    """Give a SAMPLE provider everything the ready-to-work rules ask for: verified sample documents, a
    confirmed sample guarantor, a complete profile and the current legal documents. Never for real rows."""
    from datetime import date, timedelta

    from core.crypto import encrypt
    from services import legal, vetting
    from services.db import connection

    p = svc.get(provider_id)
    if not p or not fetch_one("select is_sample from providers where id = %s", (provider_id,))["is_sample"]:
        raise SystemExit("make_ready is only for sample providers")
    today = date.today()
    extra = {
        "police_clearance": (today - timedelta(days=20), None, "FPC-SAMPLE"),
        "trade_licence": (None, today + timedelta(days=300), p.get("trade_license_no") or "AA/SAMPLE"),
        "tin_certificate": (None, None, p.get("tin") or "0000000000"),
    }
    with connection() as conn, conn.transaction():
        conn.execute("update providers set telegram_username = coalesce(telegram_username, %s), "
                     "bio = case when length(coalesce(bio, '')) < %s then %s else bio end where id = %s",
                     (f"sample_{p['slug'].replace('-', '_')[:20]}", svc.BIO_MIN,
                      "Sample provider for demos. Not a real person or business.", provider_id))
        if vetting.guarantor_applies(p) and not vetting.current_guarantor(provider_id):
            conn.execute(
                "insert into provider_guarantors (provider_id, full_name, phone, relationship, sub_city, occupation, "
                "id_number_enc, id_last4, status, checked_by, checked_at, note, created_by) values "
                "(%s, 'Sample Guarantor', '0900000000', 'Sample', 'Bole', 'Sample', %s, '0000', 'confirmed', 'seed', "
                "now(), 'Sample data', 'seed')", (provider_id, encrypt("0000000000000000")))
        g = vetting.current_guarantor(provider_id) if vetting.guarantor_applies(p) else None
        for kind in vetting.document_kinds(p):
            meta = vetting.KINDS[kind]
            if meta.optional or kind == "id_copy" or (kind == "photo" and p["entity_type"] == "company"):
                continue
            if conn.execute("select 1 from provider_documents where provider_id = %s and kind = %s "
                            "and status = 'verified'", (provider_id, kind)).fetchone():
                continue
            issued, expires, ref = extra.get(kind, (None, None, None))
            conn.execute(
                "insert into provider_documents (provider_id, kind, level, file_key, content_type, issued_on, expires_on, "
                "reference_no, status, reviewed_by, reviewed_at, review_note, uploaded_by, consent_at, guarantor_id) "
                "values (%s, %s, %s, %s, 'image/png', %s, %s, %s, 'verified', 'seed', now(), 'Sample data', 'seed', now(), %s)",
                (provider_id, kind, "degree" if kind == "education" else None, SAMPLE_FILE, issued, expires, ref,
                 g["id"] if g and meta.guarantor else None))
        legal.record_consents(conn, p["user_id"], legal.current_versions(legal.CLIENT_REQUIRED + legal.PROVIDER_REQUIRED),
                              None, "scripts/seed_providers.py")
    svc.recompute(provider_id)


def make_all_ready() -> None:
    run_migrations()
    from services.db import fetch_all

    for row in fetch_all("select id::text, display_name from providers where is_sample"):
        make_ready(row["id"])
        p = svc.get(row["id"])
        print(f"  {'ready' if p['ready_to_work'] else 'NOT ready':9s} {p['display_name']}")


def seed() -> None:
    run_migrations()
    if fetch_one("select 1 from providers where is_sample limit 1"):
        print("Sample providers already exist. Run with --purge first to reseed.")
        return
    clients = [_user(f"sample-client-{i}@sample.invalid", n) for i, n in enumerate(
        ["Abebech Lemma", "Samuel Desta", "Rahel Mulugeta", "Bereket Tsegaye", "Liya Fekadu",
         "Nahom Gebre", "Tigist Ayele", "Henok Wondimu"])]
    made: dict[str, dict] = {}

    for spec in PROVIDERS:
        spec = dict(spec)
        key, months, ratings = spec.pop("key"), spec.pop("months"), spec.pop("reviews")
        declined, member_of = spec.pop("declined"), spec.pop("member_of", None)
        license_verified, upheld = spec.pop("license_verified", None), spec.pop("disputes_upheld", 0)
        owner = _user(f"sample-{key}@sample.invalid", spec["display_name"])
        spec.setdefault("phone", f"09{random.randint(10_000_000, 99_999_999)}")
        provider = svc.join({
            **spec, "national_id_last4": str(random.randint(1000, 9999)), "national_id_verified": True,
            "id_verification_method": "fayda_sandbox", "verified_name": spec["display_name"], "is_sample": True,
        }, user_id=owner["id"], actor="seed")
        make_ready(provider["id"])
        svc.review_provider(provider["id"], "approve", actor="seed", note="Sample data, not a real provider")
        execute("update providers set approved_at = now() - make_interval(days => %s) where id = %s",
                (int(months * 30.4), provider["id"]))
        if license_verified is not None:
            svc.verify_external_license(provider["id"], "verified" if license_verified else "rejected",
                                        actor="seed", note=None if license_verified else "Licence number not found")
            if not license_verified:  # leave it waiting for staff instead of rejected
                execute("update providers set external_license_status = 'pending' where id = %s", (provider["id"],))
        made[key] = {**provider, "_owner": owner, "_ratings": ratings, "_declined": declined,
                     "_member_of": member_of, "_upheld": upheld}

    for key, p in made.items():
        if p["_member_of"]:
            agency = made[p["_member_of"]]
            m = svc.request_to_join(p["_owner"]["id"], agency["slug"], "seed")
            svc.respond_membership(agency["_owner"]["id"], m["membership_id"], "accept", "seed")

        jobs = _jobs_for(p)
        for i, rating in enumerate(p["_ratings"] + [None] * p["_declined"]):
            client = clients[(i + len(key)) % len(clients)]
            hire = svc.create_hire({
                "provider_id": p["id"], "title": jobs[i % len(jobs)], "client_name": client["fullname"],
                "client_phone": f"09{random.randint(10_000_000, 99_999_999)}",
                "client_telegram": f"sample_client_{i:02d}",
                "service_id": (p["service_ids"] or [None])[0],
            }, user_id=client["id"])
            owner_id = p["_owner"]["id"]
            if rating is None:
                svc.provider_action(hire["id"], user_id=owner_id, action="decline", reason="Fully booked this week")
            else:
                price = random.choice((p["fee_from"] or 800, p["fee_to"] or 1500))
                svc.provider_action(hire["id"], user_id=owner_id, action="accept", price=price)
                svc.provider_action(hire["id"], user_id=owner_id, action="start")
                svc.provider_action(hire["id"], user_id=owner_id, action="complete",
                                    note="Sample job: the work was delivered and the client was told.")
                # Sample jobs never carry real money: close them as paid so they can be reviewed like real ones
                execute("update engagements set client_confirmed_at = now(), payment_status = 'paid' where id = %s",
                        (hire["id"],))
                sub = lambda: max(1, min(5, rating + random.choice((-1, 0, 0, 1))))  # noqa: E731
                svc.leave_review(hire["id"], user_id=client["id"], data={
                    "rating": rating, "communication": sub(), "fee_honesty": sub(), "speed": sub(),
                    "outcome": sub(), "would_hire_again": rating >= 4,
                    "comment": random.choice(COMMENTS[rating]),
                })
            age = random.randint(5, max(6, int(p_months(key) * 30)))
            execute("update engagements set is_sample = true, created_at = now() - make_interval(days => %s), "
                    "accepted_at = case when accepted_at is not null "
                    "  then now() - make_interval(days => %s) + make_interval(hours => %s) end, "
                    "completed_at = case when completed_at is not null then now() - make_interval(days => %s) end "
                    "where id = %s", (age, age, random.randint(1, 30), max(1, age - 3), hire["id"]))
            execute("update reviews set is_sample = true, created_at = now() - make_interval(days => %s) "
                    "where engagement_id = %s", (max(1, age - 3), hire["id"]))
        if p["_upheld"]:
            last = fetch_one("select id::text from engagements where provider_id = %s and status = 'completed' "
                             "order by created_at limit 1", (p["id"],))
            execute("update engagements set disputed = true, dispute_status = 'upheld', "
                    "dispute_reason = 'Asked for extra payment', dispute_resolved_by = 'seed' where id = %s", (last["id"],))
        if key == "abay":
            first = fetch_one("select id::text from reviews where provider_id = %s order by created_at limit 1", (p["id"],))
            execute("update reviews set reply = 'Thank you! Glad the shipment cleared on time.', replied_at = now() where id = %s",
                    (first["id"],))

    for p in made.values():
        svc.recompute(p["id"])
    print(f"Seeded {len(made)} sample providers.")
    for p in sorted((svc.get(m["id"]) for m in made.values()), key=lambda x: -x["trust_score"]):
        print(f"  {p['trust_score']:3d}  {p['provider_type']:11s} {p['display_name']}  ({p['rating_count']} reviews)")


def p_months(key: str) -> float:
    return next(s["months"] for s in PROVIDERS if s["key"] == key)


if __name__ == "__main__":
    if "--make-ready" in sys.argv:
        make_all_ready()
    elif "--purge" in sys.argv:
        print(svc.purge_samples(actor="scripts/seed_providers.py"))
    else:
        seed()
