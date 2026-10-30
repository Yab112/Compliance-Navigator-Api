"""Organization data for roadmap steps."""

from __future__ import annotations

import re

from .helpers import _plain
from .public import _freshness_and_changes, _issuer_index, _live_services, _service_branches, _with_issuer


# ---------------------------------------------------------------- paths (roadmap steps)


def _norm_place(value: str | None) -> str:
    return re.sub(r"[^a-z]", "", (value or "").lower())


def org_data_for_steps(document_ids: list[str], sub_city: str | None) -> dict[str, dict]:
    """For each roadmap step (a document id), what the issuing organization published about it.

    Picks the service that issues the document, preferring one with a branch in the
    person's sub-city, and returns everything the step should show.
    """
    wanted = set(document_ids)
    if not wanted:
        return {}
    live = _live_services()
    here = _norm_place(sub_city)
    best: dict[str, tuple[int, str]] = {}
    for sid, snap in live.items():
        branches = _service_branches(snap)
        # A service offered only at branches in other sub-cities is not where this person goes
        if here and branches and all(b.get("sub_city") and _norm_place(b["sub_city"]) != here for b in branches):
            continue
        local = any(_norm_place(b.get("sub_city")) == here for b in branches) if here else False
        rank = (2 if local else 0) + (1 if branches else 0)
        for out in snap.get("outputs") or []:
            doc = out.get("document_id")
            if doc in wanted and (doc not in best or rank > best[doc][0]):
                best[doc] = (rank, sid)
    if not best:
        return {}
    index = _issuer_index(live)
    result = {}
    for doc, (_, sid) in best.items():
        snap = live[sid]
        branches = _service_branches(snap)
        branches.sort(key=lambda b: _norm_place(b.get("sub_city")) != here)
        fresh = _freshness_and_changes(sid)
        result[doc] = _plain({
            "serviceId": sid,
            "serviceName": snap["name"],
            "serviceNameAm": snap.get("name_am"),
            "orgName": snap["org"]["name"],
            "orgSlug": snap["org"]["slug"],
            "serviceSlug": snap["slug"],
            "summary": snap.get("summary"),
            "branch": branches[0] if branches else None,
            "otherBranches": len(branches) - 1 if branches else 0,
            "delivery": snap.get("delivery"),
            "onlineUrl": snap.get("online_url"),
            "onlineParts": snap.get("online_parts"),
            "isFree": snap.get("is_free"),
            "feeSchedule": snap.get("fee_schedule") or [],
            "feeAmountMin": snap.get("fee_amount_min"),
            "feeAmountMax": snap.get("fee_amount_max"),
            "feeCurrency": snap.get("fee_currency") or "ETB",
            "feeNotes": snap.get("fee_notes"),
            "paymentMethods": snap.get("payment_methods") or [],
            "whereToPay": snap.get("where_to_pay"),
            "processingTimeText": snap.get("processing_time_text"),
            "processingMinutes": snap.get("processing_minutes"),
            "requirements": [
                {k: v for k, v in _with_issuer(r, sid, live, index).items() if k not in ("key", "kind", "document_id")}
                for r in snap.get("requirements") or []
            ],
            "noDocumentsRequired": snap.get("no_documents_required"),
            "hasQuestions": bool(snap.get("questions")),
            "steps": snap.get("steps") or [],
            "appointment": {
                "required": snap.get("appointment_required"),
                "how": snap.get("appointment_how"),
                "url": snap.get("appointment_url"),
                "phone": snap.get("appointment_phone"),
            },
            "proxyAllowed": snap.get("proxy_allowed"),
            "proxyNotes": snap.get("proxy_notes"),
            "languages": snap.get("languages") or [],
            "accessibilityNotes": snap.get("accessibility_notes"),
            "legalBasis": snap.get("legal_basis"),
            "legalReferenceNumber": snap.get("legal_reference_number"),
            "forms": snap.get("forms") or [],
            "rejectionReasons": snap.get("common_rejection_reasons") or [],
            "outputValidityMonths": snap.get("output_validity_months"),
            "lateRenewalPenalty": snap.get("late_renewal_penalty"),
            "contact": {"name": snap.get("contact_name"), "phone": snap.get("contact_phone"),
                        "email": snap.get("contact_email")},
            "confirmedAt": fresh["confirmed_at"],
            "confirmedDaysAgo": fresh["confirmed_days_ago"],
            "confirmationDue": fresh["confirmation_due"],
            "upcomingChange": fresh["upcoming_change"],
        })
    return result
