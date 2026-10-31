"""
Seed SAMPLE organizations that show a cross-organization path:
Woreda resident ID -> Revenues TIN, DARS lease notarization -> Bole trade license.

Each service carries the full path data: fee schedule, documents with details, windows per
branch, weekly hours, appointments, who may apply for someone else, validity and contacts.
One service has an approved fee change scheduled for next month, and one is overdue for its
90-day confirmation, so both workflows can be seen.

Run from api/:  uv run python -m scripts.seed_organizations
Re-running replaces the sample organizations. Every record says it is sample data.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta  # noqa: E402

from schemas.organizations import ServiceIn  # noqa: E402
from services import org_service, user_store  # noqa: E402
from services.db import execute, fetch_all, fetch_one, run_migrations  # noqa: E402

SEED_EMAIL = "sample-organizations@compliance-navigator.local"
SAMPLE = "Sample data for demonstration. Not an official listing."
ACTOR = "seed script"


def _owner() -> dict:
    # No password: this account exists only to own the sample records and can't sign in
    return user_store.get_user_by_email(SEED_EMAIL) or user_store.create_user(SEED_EMAIL, "Sample data", None)


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")
# Standard federal office hours with the lunch break, and Saturday morning where offered
OFFICE_HOURS = [{"day": d, "open": "08:30", "close": "17:30", "lunch_start": "12:30", "lunch_end": "13:30"}
                for d in WEEKDAYS]
SATURDAY = [{"day": "sat", "open": "08:30", "close": "12:30"}]


def _purge(owner: dict) -> None:
    for s in fetch_all("select s.id::text from org_services s join organizations o on o.id = s.org_id "
                       "where o.created_by = %s", (owner["id"],)):
        org_service.remove_service_from_graph(s["id"])
    execute("delete from organizations where created_by = %s", (owner["id"],))


def _org(owner: dict, fields: dict) -> dict:
    org = org_service.register_org(
        {
            "representative_name": "Sample representative",
            "representative_title": "Customer service head",
            "official_email": "sample@example.gov.et",
            "steward_name": "Sample data officer",
            "steward_role": "Customer service",
            "steward_phone": "0116000000",
            "description": f"{fields.pop('about')} {SAMPLE}",
            **fields,
        },
        user_id=owner["id"],
        user_email=owner["email"],
    )
    org_service.update_org(org["id"], {"data_commitment": True}, ACTOR)
    org_service.review_org(org["id"], "verify", actor=ACTOR, note="Sample organization")
    org["branches"] = org_service.list_branches(org["id"])
    return org


def _publish(org: dict, data: dict) -> str:
    base = {
        "name_am": None, "summary": None, "who_can_apply": None, "delivery": "in_person", "online_url": None,
        "fee_amount_min": None, "fee_amount_max": None, "fee_currency": "ETB", "fee_notes": None,
        "payment_methods": [], "processing_time_text": None, "processing_minutes": None, "legal_basis": None,
        "forms": [], "common_rejection_reasons": [], "faq": [], "outputs": [],
        "requirements": [], "questions": [], "steps": [], "fee_schedule": [], "is_free": False,
        "where_to_pay": None, "no_documents_required": False, "appointment_required": False,
        "appointment_how": None, "appointment_url": None, "appointment_phone": None, "proxy_allowed": None,
        "proxy_notes": None, "online_parts": None, "languages": ["Amharic", "English"], "accessibility_notes": None,
        "audience": [], "legal_reference_number": None, "legal_effective_date": None, "contact_name": None,
        "contact_phone": None, "contact_email": None, "output_validity_months": None, "renewal_service_id": None,
        "late_renewal_penalty": None,
        # Every sample service is offered at all of the organization's branches
        "branch_ids": [b["id"] for b in org["branches"]],
        "branch_details": [{"branch_id": b["id"], "window": data.pop("window", None) or "Window 1"}
                           for b in org["branches"]],
    }
    for r in data.get("requirements", []):
        r.setdefault("kind", "prerequisite_service" if r.get("issuing_service_id") else "document")
        r.setdefault("required", "always")
        r.setdefault("original_or_copy", "original")
        for k in ("document_id", "issuing_service_id", "notes", "copies", "max_age_days", "photo_specs", "applies_to"):
            r.setdefault(k, None)
        r.setdefault("notarized", False)
        r.setdefault("translated", False)
        r.setdefault("alternatives", [])
    for q in data.get("questions", []):
        q.setdefault("type", "yes_no")
        q.setdefault("options", [])
        q.setdefault("prompt_am", None)
        for rule in q.get("rules", []):
            rule.setdefault("op", "eq")
            rule.setdefault("add_requirements", [])
            rule.setdefault("ineligible", None)
    for st in data.get("steps", []):
        for k in ("location", "description", "estimated_minutes"):
            st.setdefault(k, None)
    # Same validation and defaults as the API
    body = ServiceIn(**{**base, **data}).model_dump()
    service = org_service.save_service(org["id"], None, body, ACTOR)
    org_service.submit_service(org["id"], service["id"], ACTOR)
    _approve(service["id"])
    return service["id"]


def _approve(service_id: str) -> None:
    rev = fetch_one(
        "select id::text from org_service_revisions where service_id = %s and status = 'pending'", (service_id,)
    )
    org_service.review_submission(rev["id"], "publish", actor=ACTOR, note=SAMPLE)


def _schedule_fee_change(org: dict, service_id: str, new_fee: float, days_ahead: int) -> None:
    """An approved fee change that goes live next month, shown as 'Upcoming change' until then."""
    work = org_service.working_copy(service_id, org["id"])
    body = {k: work[k] for k in org_service.SERVICE_FIELDS}
    body.update(requirements=work["requirements"], questions=work["questions"], steps=work["steps"])
    body["fee_schedule"] = [{**row, "amount_min": new_fee} if row.get("category") == "everyone" and row.get("speed", "regular") == "regular"
                            else row for row in body["fee_schedule"]]
    org_service.save_service(org["id"], service_id, body, ACTOR)
    org_service.submit_service(org["id"], service_id, ACTOR, {
        "change_summary": f"The license fee rises to {new_fee:g} ETB under the new city tariff.",
        "change_reason": "Sample tariff revision",
        "effective_at": (date.today() + timedelta(days=days_ahead)).isoformat(),
    })
    _approve(service_id)


def main() -> None:
    run_migrations()
    owner = _owner()
    _purge(owner)

    woreda = _org(owner, {
        "name": "Bole Sub-city Woreda 03 Administration (sample)", "name_am": "ቦሌ ክፍለ ከተማ ወረዳ 03 አስተዳደር",
        "org_type": "woreda_office", "sector": "Civil registration", "region": "Addis Ababa", "sub_city": "bole",
        "phone": "0116000003", "about": "Issues resident ID cards and civil registration documents for Woreda 03.",
        "branches": [{"name": "Woreda 03 office", "sub_city": "bole", "woreda": "03",
                      "address": "Behind the woreda health center", "landmark": "Next to the Woreda 03 youth center",
                      "phone": "0116000003", "hours_schedule": OFFICE_HOURS + SATURDAY}],
    })
    revenues = _org(owner, {
        "name": "Ministry of Revenues, Bole Branch (sample)", "name_am": "የገቢዎች ሚኒስቴር ቦሌ ቅርንጫፍ",
        "org_type": "federal_institution", "sector": "Tax", "region": "Addis Ababa", "sub_city": "bole",
        "about": "Taxpayer registration and TIN certificates for businesses in Bole.",
        "branches": [{"name": "Bole branch", "sub_city": "bole", "address": "Bole Road, 2nd floor",
                      "landmark": "Across from the Bole Medhanealem church", "phone": "0116000010",
                      "hours_schedule": OFFICE_HOURS}],
    })
    dars = _org(owner, {
        "name": "DARS Bole Branch (sample)", "name_am": "የሰነዶች ማረጋገጫና ምዝገባ አገልግሎት ቦሌ",
        "org_type": "federal_institution", "sector": "Legal documents", "region": "Addis Ababa", "sub_city": "bole",
        "about": "Authenticates and registers contracts, including lease agreements.",
        "branches": [{"name": "Bole branch", "sub_city": "bole", "address": "Africa Avenue",
                      "phone": "0116000020", "hours_schedule": OFFICE_HOURS + SATURDAY}],
    })
    trade = _org(owner, {
        "name": "Bole Sub-city Trade Office (sample)", "name_am": "ቦሌ ክፍለ ከተማ ንግድ ጽ/ቤት",
        "org_type": "sub_city_office", "sector": "Trade", "region": "Addis Ababa", "sub_city": "bole",
        "about": "Issues and renews trade licenses for businesses operating in Bole.",
        "branches": [{"name": "Trade office, ground floor", "sub_city": "bole",
                      "address": "Bole Sub-city administration building", "landmark": "Main gate, turn left",
                      "phone": "0116000030", "hours_schedule": OFFICE_HOURS}],
    })

    resident_id = _publish(woreda, {
        "name": "Resident ID card", "name_am": "የነዋሪነት መታወቂያ", "window": "Window 3",
        "summary": "New resident ID card for people living in Woreda 03.",
        "who_can_apply": "Residents aged 18 or older registered in the woreda.", "audience": ["citizen", "resident"],
        "fee_schedule": [{"category": "everyone", "amount_min": 50, "covers": "ID card and lamination"}],
        "payment_methods": ["Cash"], "where_to_pay": "Cashier next to Window 1",
        "processing_time_text": "Same day", "processing_minutes": 60,
        "proxy_allowed": "no", "proxy_notes": "Fingerprints and photo are taken in person.",
        "output_validity_months": 24, "late_renewal_penalty": "50 ETB if renewed after expiry",
        "outputs": [{"name": "Resident ID card", "document_id": "kebele_id"}],
        "legal_basis": "Addis Ababa resident registration directive",
        "contact_name": "Civil registration desk", "contact_phone": "0116000003",
        "requirements": [
            {"key": "birth", "name": "Birth certificate or witness affidavit", "document_id": "birth_certificate",
             "alternatives": ["Witness affidavit signed by two residents"]},
            {"key": "photos", "name": "Passport-size photographs", "copies": 2,
             "photo_specs": "3x4 cm, white background, taken in the last 6 months"},
            {"key": "address", "name": "Proof of address (house rent contract or ownership)", "original_or_copy": "both",
             "max_age_days": 90},
        ],
        "steps": [
            {"title": "Fill the registration form", "location": "Window 1", "estimated_minutes": 15},
            {"title": "Photo and fingerprint", "location": "Window 3", "estimated_minutes": 20},
            {"title": "Collect the ID", "location": "Window 1", "estimated_minutes": 25},
        ],
        "common_rejection_reasons": ["Photo older than 6 months", "Address proof not in the applicant's name"],
    })
    tin = _publish(revenues, {
        "name": "TIN registration", "name_am": "የግብር ከፋይ መለያ ቁጥር ምዝገባ", "window": "Registration desk",
        "summary": "Register as a taxpayer and receive a TIN certificate.",
        "who_can_apply": "Individuals starting a business and companies registering in Bole.",
        "audience": ["citizen", "company", "investor"],
        "fee_schedule": [{"category": "everyone", "amount_min": 100, "covers": "TIN certificate"}],
        "payment_methods": ["Cash", "Telebirr"], "where_to_pay": "Cashier on the 2nd floor",
        "processing_time_text": "About 30 minutes", "processing_minutes": 30,
        "proxy_allowed": "with_poa", "proxy_notes": "Bring a notarized power of attorney and the agent's ID.",
        "outputs": [{"name": "TIN certificate", "document_id": "tin"}],
        "legal_basis": "Federal Tax Administration Proclamation", "legal_reference_number": "983/2016",
        "contact_phone": "0116000010",
        "requirements": [
            {"key": "id", "name": "Resident ID card", "issuing_service_id": resident_id, "original_or_copy": "both",
             "applies_to": "applicant"},
            {"key": "form", "name": "Completed IT-101 form"},
        ],
        "common_rejection_reasons": ["Name on the form differs from the ID card"],
        "steps": [{"title": "Submit form and ID", "location": "Registration desk", "estimated_minutes": 30}],
    })
    lease = _publish(dars, {
        "name": "Lease agreement notarization", "name_am": "የኪራይ ውል ማረጋገጫ", "window": "Window 2",
        "summary": "Authenticate a lease agreement for business premises.",
        "audience": ["citizen", "company", "foreigner"],
        "fee_schedule": [
            {"category": "ethiopian", "amount_min": 200, "covers": "Per copy", "notes": "Plus 0.5% of the rent for the contract period"},
            {"category": "foreign_national", "amount_min": 400, "covers": "Per copy", "notes": "Plus 0.5% of the rent for the contract period"},
            {"category": "ethiopian", "speed": "urgent", "amount_min": 400, "covers": "Same-hour service"},
        ],
        "payment_methods": ["Cash", "CBE Birr"], "processing_time_text": "About 45 minutes", "processing_minutes": 45,
        "appointment_required": True, "appointment_how": "Book a slot online or by phone the day before",
        "appointment_url": "https://example.gov.et/book", "appointment_phone": "0116000020",
        "proxy_allowed": "with_poa", "languages": ["Amharic", "English", "Afaan Oromo"],
        "accessibility_notes": "Ground floor service window for people with limited mobility.",
        "outputs": [{"name": "Notarized lease agreement", "document_id": "notarized_lease"}],
        "requirements": [
            {"key": "lease", "name": "Original lease agreement", "copies": 3, "applies_to": "each_party"},
            {"key": "id", "name": "Resident ID card of both parties", "issuing_service_id": resident_id,
             "original_or_copy": "both", "applies_to": "each_party"},
            {"key": "consent", "name": "Owner consent if the signer is not the owner", "required": "conditional",
             "notarized": True},
        ],
        "questions": [
            {"key": "owner_signs", "prompt": "Will the property owner sign in person?", "prompt_am": "ባለቤቱ በአካል ይፈርማሉ?",
             "rules": [{"value": "no", "add_requirements": ["consent"]}]},
        ],
        "steps": [
            {"title": "Check the contract and IDs", "location": "Window 2", "estimated_minutes": 15},
            {"title": "Pay", "location": "Cashier", "estimated_minutes": 10},
            {"title": "Sign before the officer and collect", "location": "Window 2", "estimated_minutes": 20},
        ],
    })
    license_id = _publish(trade, {
        "name": "New trade license", "name_am": "አዲስ የንግድ ፈቃድ", "window": "Window 2",
        "summary": "First trade license for a business operating in Bole sub-city.",
        "who_can_apply": "Sole proprietors and companies with premises in Bole.",
        "audience": ["company", "investor", "citizen"],
        "fee_schedule": [{"category": "everyone", "amount_min": 302, "covers": "License certificate"}],
        "payment_methods": ["Cash", "Telebirr", "CBE Birr"], "where_to_pay": "Cashier window, ground floor",
        "processing_time_text": "About 15 minutes after documents are accepted", "processing_minutes": 15,
        "proxy_allowed": "with_poa", "output_validity_months": 12,
        "late_renewal_penalty": "Renewal after expiry adds a penalty set by the trade bureau",
        "outputs": [{"name": "Trade license", "document_id": "trade_license"}],
        "legal_basis": "Commercial Registration and Business Licensing Proclamation",
        "legal_reference_number": "1150/2019", "contact_name": "Licensing desk", "contact_phone": "0116000030",
        "requirements": [
            {"key": "tin", "name": "TIN certificate", "issuing_service_id": tin, "original_or_copy": "both"},
            {"key": "id", "name": "Resident ID card", "issuing_service_id": resident_id, "original_or_copy": "both"},
            {"key": "lease", "name": "Notarized lease agreement", "issuing_service_id": lease, "required": "conditional"},
            {"key": "title", "name": "Title deed of the premises", "required": "conditional", "original_or_copy": "both"},
            {"key": "permit", "name": "Work permit and investment permit", "required": "conditional", "translated": True},
        ],
        "questions": [
            {"key": "renting", "prompt": "Are you renting the premises?", "prompt_am": "ቦታውን ተከራይተዋል?",
             "rules": [{"value": "yes", "add_requirements": ["lease"]}, {"value": "no", "add_requirements": ["title"]}]},
            {"key": "foreign", "prompt": "Is the owner a foreign national?", "prompt_am": "ባለቤቱ የውጭ ዜጋ ነው?",
             "rules": [{"value": "yes", "add_requirements": ["permit"]}]},
        ],
        "steps": [
            {"title": "Check documents", "location": "Window 2", "estimated_minutes": 10},
            {"title": "Pay the fee", "location": "Cashier", "estimated_minutes": 5},
            {"title": "Receive the license", "location": "Window 2", "estimated_minutes": 5},
        ],
        "common_rejection_reasons": ["Lease not notarized", "TIN name differs from license application"],
        "faq": [{"q": "Can someone apply for me?", "a": "Yes, with a notarized power of attorney."}],
    })
    _schedule_fee_change(trade, license_id, 350, days_ahead=30)
    # Overdue for its 90-day check, so the dashboard and public page show the reminder
    execute("update org_services set last_confirmed_at = now() - interval '100 days' where id = %s", (resident_id,))
    print("Sample organizations ready: woreda, revenues, DARS, trade office.")


if __name__ == "__main__":
    main()
