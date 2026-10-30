"""Trust score (0-100) for marketplace providers, with a breakdown anyone can read.

Weights, chosen so reputation from real hires dominates but a new, fully verified
provider still starts above an unverified one:

  rating          50  Bayesian average of review ratings (prior 3.5 stars, weight 5)
  verification    25  Fayda ID 8, phone 2, police clearance 5 (checked by staff, in date),
                      education 3 (individuals: certificate at the required level, checked by staff),
                      TIN 3 for individuals or TIN and trade licence 6 for companies, sector licence 4.
                      Changed when vetting documents were added: clearance and education took points
                      from the other checks, so the part and the total stay at 25 and 100.
  reliability     15  completed vs declined or abandoned jobs (smoothed)
  experience      10  completed jobs (up to 20) and months on the platform (up to 24)
  penalties      -30  upheld disputes (-10 each), suspensions (-5 each, max -15)
"""

from __future__ import annotations

from datetime import datetime, timezone

PRIOR_RATING = 3.5
PRIOR_WEIGHT = 5
NEW_UNTIL_REVIEWS = 3
RELIABILITY_PRIOR = 0.8
RELIABILITY_WEIGHT = 3


def bayesian_rating(total_stars: float, count: int) -> float:
    return (PRIOR_WEIGHT * PRIOR_RATING + total_stars) / (PRIOR_WEIGHT + count)


def compute(stats: dict) -> dict:
    """`stats` keys: review_count, review_sum, fayda_verified, has_phone, has_tin,
    has_trade_license, entity_type, external_license_verified, completed, failed,
    approved_at, upheld_disputes, suspensions; optional police_clearance_verified, education_verified."""
    parts: list[dict] = []

    bayes = bayesian_rating(stats["review_sum"], stats["review_count"])
    rating_pts = (bayes - 1) / 4 * 50
    parts.append({
        "key": "rating", "label": "Client ratings", "max": 50, "points": rating_pts,
        "detail": (
            f"{stats['review_count']} verified review{'s' if stats['review_count'] != 1 else ''}, "
            f"adjusted average {bayes:.2f} of 5"
        ),
    })

    verification = 0
    checks = []
    company = stats["entity_type"] == "company"
    if stats["fayda_verified"]:
        verification += 8
        checks.append("Fayda ID")
    if stats["has_phone"]:
        verification += 2
        checks.append("phone")
    if stats.get("police_clearance_verified"):
        verification += 5
        checks.append("police clearance")
    if stats.get("education_verified") and not company:
        verification += 3
        checks.append("education")
    registered = stats["has_tin"] and (stats["has_trade_license"] or not company)
    if registered:
        verification += 6 if company else 3
        checks.append("TIN and trade licence" if company else "TIN")
    if stats["external_license_verified"]:
        verification += 4
        checks.append("sector licence")
    parts.append({
        "key": "verification", "label": "Verification", "max": 25, "points": verification,
        "detail": ("Verified: " + ", ".join(checks)) if checks else "Nothing verified yet",
    })

    done, failed = stats["completed"], stats["failed"]
    reliability = (done + RELIABILITY_PRIOR * RELIABILITY_WEIGHT) / (done + failed + RELIABILITY_WEIGHT)
    parts.append({
        "key": "reliability", "label": "Reliability", "max": 15, "points": reliability * 15,
        "detail": f"{done} completed, {failed} declined or dropped",
    })

    months = 0.0
    if stats.get("approved_at"):
        approved = stats["approved_at"]
        if approved.tzinfo is None:
            approved = approved.replace(tzinfo=timezone.utc)
        months = max(0.0, (datetime.now(timezone.utc) - approved).days / 30.4)
    experience = min(done, 20) / 20 * 6 + min(months, 24) / 24 * 4
    parts.append({
        "key": "experience", "label": "Track record", "max": 10, "points": experience,
        "detail": f"{done} jobs on the platform, {int(months)} months active",
    })

    penalty = min(stats["upheld_disputes"] * 10, 30) + min(stats["suspensions"] * 5, 15)
    penalty = min(penalty, 30)
    if penalty:
        parts.append({
            "key": "penalties", "label": "Penalties", "max": 0, "points": -penalty,
            "detail": f"{stats['upheld_disputes']} upheld complaints, {stats['suspensions']} suspensions",
        })

    total = round(max(0, min(100, sum(p["points"] for p in parts))))
    for p in parts:
        p["points"] = round(p["points"], 1)
    return {
        "score": total,
        "is_new": stats["review_count"] < NEW_UNTIL_REVIEWS,
        "rating_adjusted": round(bayes, 2),
        "parts": parts,
    }


def _doc_tip(status: str | None, what: str, points: int) -> str | None:
    """What to do about one vetting document, from its status on the Documents tab."""
    if status == "pending":
        return f"Staff are checking your {what}. It adds {points} points once approved."
    if status == "rejected":
        return f"Your {what} was not accepted. Upload a new copy on the Documents tab (+{points})."
    if status == "expired":
        return f"Your {what} has expired. Upload a new one on the Documents tab (+{points})."
    if status == "below_minimum":
        return f"Upload a higher {what} on the Documents tab (+{points})."
    if status in ("verified", "expiring"):
        return None
    return f"Upload your {what} on the Documents tab (+{points})."


def tips(breakdown: dict, provider: dict, doc_status: dict[str, str] | None = None) -> list[str]:
    """Concrete next steps shown to the provider on their own dashboard. doc_status maps a vetting
    document kind to its checklist status, so a tip never asks for something already uploaded."""
    out = []
    doc_status = doc_status or {}
    by_key = {p["key"]: p for p in breakdown["parts"]}
    if by_key["verification"]["points"] < 25:
        company = provider["entity_type"] == "company"
        done = (by_key["verification"].get("detail") or "").lower()
        if not (provider.get("national_id_verified") or provider.get("id_verified")):
            out.append("Verify your identity with Fayda (+8).")
        doc_tips = []
        if "police clearance" not in done:
            doc_tips.append(_doc_tip(doc_status.get("police_clearance"), "police clearance", 5))
        if not company and "education" not in done:
            doc_tips.append(_doc_tip(doc_status.get("education"), "education certificate", 3))
        out.extend(t for t in doc_tips if t)
        if not provider.get("tin"):
            out.append("Add your TIN" + (" and trade licence" if company else "") + f" (+{6 if company else 3}).")
        licence = provider.get("external_license_status")
        if licence == "pending":
            out.append("Staff are checking your sector licence. It adds 4 points once verified.")
        elif licence == "rejected":
            out.append("Your sector licence could not be verified. Correct the number on the Edit profile tab (+4).")
        elif licence != "verified":
            out.append("Add your sector licence number on the Edit profile tab so staff can verify it (+4).")
    if breakdown["is_new"]:
        out.append("Complete your first jobs and ask clients to leave a review. Ratings are half of the score.")
    if by_key["reliability"]["points"] < 12:
        out.append("Accept only jobs you can finish. Declined and dropped jobs lower reliability.")
    return out
