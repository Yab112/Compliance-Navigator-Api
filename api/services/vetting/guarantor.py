"""The guarantor (ተያዥ): their details, their papers and the staff phone check."""

from __future__ import annotations

from services.db import connection, fetch_all, fetch_one
from services.vetting.common import (
    _clean_text,
    _notify_provider,
    _recompute,
    _uuid_like,
)
from services.vetting.rules import (
    GUARANTOR_KINDS,
    VettingError,
    _doc_item,
    guarantor_applies,
    guarantor_required,
)

# ---------------------------------------------------------------- guarantor (ተያዥ)

# In Ethiopia a guarantor (ተያዥ) signs that they will answer for a worker's conduct and losses, as
# employers ask of cashiers, drivers and domestic workers. Usually an employed person (with an employer
# letter stating their salary) or a property owner; the letter is often authenticated at the Documents
# Authentication and Registration Service; and the employer phones the guarantor to confirm.
GUARANTOR_HELP = (
    "A guarantor (ተያዥ) is someone who signs that they will answer for your conduct and for losses you cause "
    "a client, as employers in Ethiopia often ask. Choose an adult who knows you well and has a steady job "
    "or owns property. They sign a guarantee letter (better if it is authenticated at the Documents "
    "Authentication and Registration Service), and our staff will phone them to confirm they signed it "
    "knowingly. Ask them first: you share their name, phone and ID number with us."
)
GUARANTOR_STAFF_HELP = (
    "Call the guarantor on the phone number given (not one the provider passes you on the day). Confirm "
    "their full name and the last 4 digits of their ID, that they know the provider and how, that they "
    "signed the guarantee letter themselves and understand they answer for losses up to the amount in it, "
    "and where they work. Check the letter's Documents Authentication and Registration Service stamp and "
    "number when it has one. Confirm only when the call and the papers agree; write what you checked."
)
GUARANTOR_COLUMNS = ("id::text, provider_id::text, full_name, phone, relationship, sub_city, woreda, address, "
                     "occupation, employer, id_last4, status, checked_by, checked_at, note, created_by, created_at, "
                     "superseded_at")


def current_guarantor(provider_id: str) -> dict | None:
    return fetch_one(
        f"select {GUARANTOR_COLUMNS} from provider_guarantors where provider_id = %s and status <> 'superseded'",
        (provider_id,),
    )


def guarantor_history(provider_id: str) -> list[dict]:
    """Replaced guarantors, kept on file, newest first (staff only)."""
    return fetch_all(
        f"select {GUARANTOR_COLUMNS} from provider_guarantors where provider_id = %s and status = 'superseded' "
        "order by created_at desc limit 20",
        (provider_id,),
    )


def _guarantor_item(provider: dict, docs: list[dict], max_age: int, *, for_staff: bool) -> dict:
    """Verified only when staff confirmed the guarantor by phone AND the letter and ID copy are verified."""
    g = current_guarantor(provider["id"])
    papers = [_doc_item(provider, k, docs, max_age, for_staff=for_staff) for k in GUARANTOR_KINDS]
    needed = [d for d in papers if d["required"]]
    papers_ok = all(d["status"] in ("verified", "expiring") for d in needed)
    if not g:
        status, message = "missing", "Add your guarantor's details, then upload the signed letter and their ID."
    elif g["status"] == "failed":
        status = "rejected"
        message = "We could not confirm your guarantor" + (f": {g['note']}" if g.get("note") else ".") + \
            " Add another guarantor or correct the details."
    elif any(d["status"] in ("rejected", "expired") for d in needed):
        status, message = "rejected", "A guarantor paper was not accepted. Upload a new copy."
    elif g["status"] == "confirmed" and papers_ok:
        status, message = "verified", None
    elif any(d["status"] == "missing" for d in needed):
        status, message = "missing", "Upload the signed guarantee letter and your guarantor's ID."
    else:
        status = "pending"
        message = "Staff will phone your guarantor and check the papers." if g["status"] == "pending" \
            else "Guarantor confirmed. Staff will check the papers."
    if g:
        g = dict(g)
        if not for_staff:
            # The provider sees what they entered; staff's call notes stay internal unless it failed
            g.pop("checked_by", None)
            if g["status"] != "failed":
                g.pop("note", None)
    item = {
        "key": "guarantor", "type": "guarantor", "label": "Guarantor", "label_am": "ተያዥ",
        "required": guarantor_required(provider), "status": status, "message": message,
        "help": GUARANTOR_HELP, "guarantor": g, "documents": papers,
    }
    if for_staff:
        item["how_to_verify"] = GUARANTOR_STAFF_HELP
        item["history"] = guarantor_history(provider["id"])
    return item


def _clean_id_number(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isalnum())
    if not 6 <= len(digits) <= 32:
        raise VettingError("Enter the guarantor's national ID or Fayda number (6 to 32 letters and digits)")
    return digits


def set_guarantor(provider: dict, data: dict, *, actor: str, consent: bool) -> dict:
    """Add or change the guarantor. The same person (same ID number) is updated in place and keeps their
    papers; a different person replaces the old one, whose record and papers stay on file as superseded.
    Either way a change goes back to staff to confirm."""
    from core.crypto import decrypt, encrypt

    if not guarantor_applies(provider):
        raise VettingError("A guarantor isn't needed for your kind of profile")
    if not consent:
        raise VettingError("Tick the box to confirm your guarantor agreed that you share their details with us")
    fields = {k: _clean_text(data.get(k), limit) for k, limit in (
        ("full_name", 120), ("phone", 20), ("relationship", 80), ("sub_city", 80), ("woreda", 40),
        ("address", 200), ("occupation", 120), ("employer", 160))}
    for k, label in (("full_name", "full name"), ("phone", "phone number"), ("relationship", "relationship to you"),
                     ("occupation", "occupation"), ("sub_city", "sub-city or town")):
        if not fields[k]:
            raise VettingError(f"Enter your guarantor's {label}")
    if provider.get("phone") and fields["phone"] == provider["phone"]:
        raise VettingError("Your guarantor needs their own phone number, not yours")
    if (fields["full_name"] or "").lower() == (provider.get("display_name") or "").lower() or \
            (provider.get("verified_name") and fields["full_name"].lower() == provider["verified_name"].lower()):
        raise VettingError("You can't be your own guarantor")
    id_number = _clean_id_number(data.get("id_number") or "")
    current = fetch_one(
        "select id::text, id_number_enc, status, full_name, phone, relationship, sub_city, woreda, address, "
        "occupation, employer from provider_guarantors where provider_id = %s and status <> 'superseded'",
        (provider["id"],),
    )
    same_person = bool(current and decrypt(current["id_number_enc"]) == id_number)
    with connection() as conn, conn.transaction():
        if same_person:
            changed = [k for k, v in fields.items() if v != current[k]]
            if not changed:
                return current_guarantor(provider["id"])
            assignments = ", ".join(f"{k} = %({k})s" for k in fields)
            # Different details need a new call; a failed check can be retried with corrected details
            conn.execute(
                f"update provider_guarantors set {assignments}, status = 'pending', checked_by = null, "
                "checked_at = null, note = null where id = %(id)s",
                {**fields, "id": current["id"]},
            )
            note = f"{fields['full_name']}: changed {', '.join(changed)}"
            action = "guarantor_updated"
        else:
            if current:
                conn.execute("update provider_guarantors set status = 'superseded', superseded_at = now() where id = %s",
                             (current["id"],))
                # The old guarantor's papers stay on file but no longer count
                conn.execute(
                    "update provider_documents set status = 'superseded' where provider_id = %s "
                    "and kind = any(%s) and status <> 'superseded'",
                    (provider["id"], list(GUARANTOR_KINDS)),
                )
            conn.execute(
                """
                insert into provider_guarantors (provider_id, full_name, phone, relationship, sub_city, woreda, address,
                  occupation, employer, id_number_enc, id_last4, created_by)
                values (%(pid)s, %(full_name)s, %(phone)s, %(relationship)s, %(sub_city)s, %(woreda)s, %(address)s,
                  %(occupation)s, %(employer)s, %(enc)s, %(last4)s, %(actor)s)
                """,
                {**fields, "pid": provider["id"], "enc": encrypt(id_number), "last4": id_number[-4:], "actor": actor},
            )
            note = f"{fields['full_name']}, ID ending {id_number[-4:]}" + (" (replaced the previous guarantor)" if current else "")
            action = "guarantor_replaced" if current else "guarantor_added"
        conn.execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
            (provider["id"], action, actor, note),
        )
    _recompute(provider["id"])
    return current_guarantor(provider["id"])


def check_guarantor(provider_id: str, guarantor_id: str, decision: str, *, actor: str, note: str | None) -> dict:
    """Staff phoned the guarantor: confirmed (they knowingly signed) or failed (with what happened)."""
    if decision not in ("confirmed", "failed"):
        raise VettingError("Choose confirmed or failed")
    note = (note or "").strip()
    if decision == "confirmed" and len(note) < 10:
        raise VettingError("Write what you confirmed on the call (at least 10 characters)")
    if decision == "failed" and len(note) < 5:
        raise VettingError("Write what happened on the call. The provider sees this.")
    if not (_uuid_like(guarantor_id) and _uuid_like(provider_id)):
        raise VettingError("Guarantor not found", 404)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "update provider_guarantors set status = %s, checked_by = %s, checked_at = now(), note = %s "
            "where id = %s and provider_id = %s and status <> 'superseded' returning full_name",
            (decision, actor, note, guarantor_id, provider_id),
        ).fetchone()
        if not row:
            raise VettingError("Guarantor not found, or replaced by a newer one", 404)
        conn.execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
            (provider_id, f"guarantor_{decision}", actor, f"{row['full_name']}: {note}"),
        )
    _notify_provider(provider_id, "Your guarantor was confirmed" if decision == "confirmed"
                     else "We could not confirm your guarantor", None if decision == "confirmed" else note)
    _recompute(provider_id)
    return current_guarantor(provider_id)
