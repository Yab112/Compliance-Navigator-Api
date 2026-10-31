"""Staff tools for providers: list, detail, review, licences and sample data."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from services import id_verification, platform_settings, vetting
from services.db import connection, execute, fetch_all, fetch_one

from .common import (
    ACTIVE_ENGAGEMENT,
    ADMIN_ACTIONS,
    ADMIN_LIST_COLUMNS,
    READY,
    REG_PREFIX,
    TODAY,
    MarketplaceError,
    _log,
    get,
)
from .engagements import _event
from .profile import _readiness_view, _services, _update, names_differ, pending_change
from .public import list_reviews
from .readiness import readiness
from .teams import agency_of, team
from .trust import recompute

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- admin


ADMIN_SORTS = {
    # The vetting queue first: pending applications and licences, oldest waiting first
    "queue": "case p.status when 'pending' then 0 else 1 end, "
             "case p.external_license_status when 'pending' then 0 else 1 end, p.created_at",
    "newest": "p.created_at desc",
    "score": "p.trust_score desc nulls last, p.created_at desc",
    "complaints": "open_disputes desc, p.created_at desc",
    "expiry": "p.license_expires_at nulls last, p.created_at",
}


def admin_list(
    *, provider_type: str | None = None, status: str | None = None, q: str | None = None,
    license_status: str | None = None, expiring_days: int | None = None, area: str | None = None,
    id_verified: bool | None = None, accepting_work: bool | None = None, sort: str = "queue",
    limit: int = 50, offset: int = 0, ready: bool | None = None,
) -> dict:
    where, params = ["true"], {}
    if ready is not None:
        where.append(READY if ready else f"not ({READY})")
    if provider_type:
        where.append("p.provider_type = %(t)s")
        params["t"] = provider_type
    if status:
        where.append("p.status = %(status)s")
        params["status"] = status
    if license_status:
        where.append("p.external_license_status = %(ls)s")
        params["ls"] = license_status
    if expiring_days is not None:
        where.append(f"p.status = 'approved' and p.license_expires_at between {TODAY} and {TODAY} + %(days)s::int")
        params["days"] = expiring_days
    if area:
        where.append("(p.sub_city = %(area)s or %(area)s = any(p.service_areas))")
        params["area"] = area
    if id_verified is not None:
        where.append("p.national_id_verified = %(idv)s")
        params["idv"] = id_verified
    if accepting_work is not None:
        where.append("p.accepting_work = %(acc)s")
        params["acc"] = accepting_work
    if q:
        # Staff may search by national ID or TIN, but the list never sends them back. Only a hash of the
        # ID is stored, so the full number must match exactly; four characters match the last four.
        id_hash, _ = id_verification.id_hash_and_last4(q)
        clean_id = id_verification.normalize_id(q)
        where.append(
            "(p.display_name ilike %(q)s or p.legal_name ilike %(q)s or p.phone ilike %(q)s "
            "or p.registration_no ilike %(q)s or p.tin ilike %(q)s or p.national_id_hash = %(id_hash)s "
            "or (length(%(id_last4)s) = 4 and p.national_id_last4 = %(id_last4)s))"
        )
        params |= {"q": f"%{q}%", "id_hash": id_hash or "", "id_last4": clean_id if len(clean_id) == 4 else ""}
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from providers p where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select * from (
          select {ADMIN_LIST_COLUMNS},
            (select count(*) from engagements e where e.provider_id = p.id
               and e.status = any(array['requested','accepted','in_progress'])) as open_jobs,
            (select count(*) from engagements e where e.provider_id = p.id and e.disputed
               and e.dispute_status = 'open') as open_disputes
          from providers p where {clause}
        ) p
        order by {ADMIN_SORTS.get(sort, ADMIN_SORTS["queue"])}
        limit %(limit)s offset %(offset)s
        """,
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": items}


def admin_detail(provider_id: str) -> dict | None:
    provider = get(provider_id)
    if not provider:
        return None
    provider["events"] = fetch_all(
        "select id, action, actor, note, created_at from provider_events "
        "where provider_id = %s order by created_at desc limit 100",
        (provider_id,),
    )
    provider["engagements"] = fetch_all(
        "select id::text, title, client_name, service_name, status, disputed, dispute_status, created_at "
        "from engagements where provider_id = %s order by created_at desc limit 50",
        (provider_id,),
    )
    provider["reviews"] = list_reviews(provider_id, limit=50, include_hidden=True)
    provider["services"] = _services(provider["service_ids"])
    provider["team"] = team(provider_id, include_pending=True)
    provider["agency"] = agency_of(provider_id, include_pending=True)
    provider["renewal"] = {"opens_on": renewal_opens_on(provider), "blocker": renewal_blocker(provider)}
    provider["vetting"] = vetting.checklist(provider, for_staff=True)
    provider["readiness"] = _readiness_view(provider)
    provider["pending_change"] = pending_change(provider_id)
    # What Fayda returned when this person verified their national ID: the proof of identity
    provider["identity"] = fetch_one(
        """
        select method, id_type, id_last4, verified_name, birthdate, gender, phone, verified_at
        from id_verifications where user_id = %s and status = 'verified' order by verified_at desc limit 1
        """,
        (provider["user_id"],),
    ) if provider.get("user_id") else None
    provider["name_mismatch"] = names_differ(provider["display_name"], provider.get("verified_name")) \
        if provider["entity_type"] == "individual" else False
    return provider


def _next_registration_no(conn, provider_type: str) -> str:
    seq = conn.execute("select nextval('provider_registration_seq') as n").fetchone()["n"]
    return f"{REG_PREFIX[provider_type]}-{date.today().year}-{seq:05d}"


def review_provider(provider_id: str, action: str, *, actor: str, note: str | None = None) -> dict:
    if action not in ADMIN_ACTIONS:
        raise MarketplaceError(f"Unknown action '{action}'")
    allowed_from, new_status = ADMIN_ACTIONS[action]
    provider = get(provider_id)
    if not provider:
        raise MarketplaceError("Provider not found", 404)
    if provider["status"] not in allowed_from:
        raise MarketplaceError(f"Cannot {action} a provider that is {provider['status']}", 409)
    if action in ("reject", "suspend") and not note:
        raise MarketplaceError(f"A reason is required to {action}")
    if action in ("approve", "renew") and len((note or "").strip()) < 10:
        # The audit log is the proof: say what was checked (ID, licence, references)
        raise MarketplaceError(f"Write what you checked before you {action} (at least 10 characters)")
    old_expiry = provider.get("license_expires_at")
    if action == "renew":
        blocker = renewal_blocker(provider)
        if blocker:
            raise MarketplaceError(blocker, 409)
    if action == "approve":
        # Every required document checked and in date before anyone is listed (services/vetting.py),
        # and the profile and agreements complete (the same rules that keep them listed afterwards)
        blocker = vetting.blocker(provider)
        if blocker:
            raise MarketplaceError(blocker, 409)
        other = [r["label"] for r in readiness(provider)["reasons"] if r["fix"] in ("profile", "agreement")]
        if other:
            raise MarketplaceError("Not ready to approve: " + "; ".join(other) + ".", 409)
    if action == "reinstate":
        blocker = vetting.expired_blocker(provider)
        if blocker:
            raise MarketplaceError(blocker, 409)

    with connection() as conn, conn.transaction():
        updates = {"reviewed_by": actor, "review_note": note}
        if new_status:
            updates["status"] = new_status
        if action in ("approve", "renew", "reinstate"):
            updates["license_expires_at"] = date.today() + timedelta(days=platform_settings.get_int("license_validity_days"))
        if action == "approve":
            if not provider["registration_no"]:
                updates["registration_no"] = _next_registration_no(conn, provider["provider_type"])
            if not provider["approved_at"]:
                conn.execute("update providers set approved_at = now() where id = %s", (provider_id,))
        assignments = ", ".join(f"{k} = %({k})s" for k in updates)
        conn.execute(
            f"update providers set {assignments}, reviewed_at = now(), updated_at = now() where id = %(id)s",
            {**updates, "id": provider_id},
        )
        if action in ("approve", "reinstate") and provider["user_id"]:
            conn.execute("update users set role = 'agent' where id = %s and role = 'user'", (provider["user_id"],))
        if action == "suspend":
            # A suspended provider can't keep client work: send it back to staff, with a line in each hire's history
            moved = conn.execute(
                "update engagements set provider_id = null, status = 'open', updated_at = now(), "
                "admin_note = coalesce(admin_note || E'\\n', '') || 'Provider suspended. Reassign.' "
                "where provider_id = %s and status = any(%s) returning id::text, status",
                (provider_id, list(ACTIVE_ENGAGEMENT)),
            ).fetchall()
            for hire in moved:
                _event(conn, hire["id"], "provider_suspended", who="staff", actor=actor, to_status="open",
                       provider_id=provider_id, note="Provider suspended; job sent back to staff to reassign")
        if action in ("approve", "renew", "reinstate"):
            # Keep the before and after in the log so a renewal can be traced
            note = f"{note or ''} (valid until {old_expiry or 'not set'} -> {updates['license_expires_at']})".strip()
        _log(conn, provider_id, action, actor, note)
    recompute(provider_id)
    return get(provider_id)


def renewal_opens_on(provider: dict) -> date | None:
    """A listing can be renewed from this many days before it expires (platform setting license_renew_window_days)."""
    expires = provider.get("license_expires_at")
    if not expires:
        return None
    return expires - timedelta(days=platform_settings.get_int("license_renew_window_days"))


def renewal_blocker(provider: dict) -> str | None:
    """Why a listing can't be renewed now, or None. Renewing early or twice proves nothing, so it isn't allowed."""
    opens = renewal_opens_on(provider)
    if opens and date.today() < opens:
        return (f"The listing is valid until {provider['license_expires_at']:%d %b %Y}. "
                f"Renewal opens on {opens:%d %b %Y}.")
    if provider["entity_type"] == "individual" and not provider.get("id_verified"):
        return "Verify the provider's national ID with Fayda before renewing."
    if provider["entity_type"] != "individual" and not provider.get("trade_license_no"):
        return "Add the company's trade licence number before renewing."
    return vetting.blocker(provider)


def verify_external_license(provider_id: str, decision: str, *, actor: str, note: str | None) -> dict:
    provider = get(provider_id)
    if not provider:
        raise MarketplaceError("Provider not found", 404)
    if not provider["external_license_no"]:
        raise MarketplaceError("This provider hasn't entered a sector licence", 409)
    if decision == "rejected" and not note:
        raise MarketplaceError("A reason is required to reject a licence")
    with connection() as conn, conn.transaction():
        conn.execute(
            "update providers set external_license_status = %s, external_license_verified_by = %s, "
            "external_license_verified_at = now(), updated_at = now() where id = %s",
            (decision, actor, provider_id),
        )
        _log(conn, provider_id, f"license_{decision}", actor, note)
    recompute(provider_id)
    return get(provider_id)


def admin_update(provider_id: str, data: dict, actor: str) -> dict:
    provider = get(provider_id)
    if not provider:
        raise MarketplaceError("Provider not found", 404)
    return _update(provider, data, actor, by_owner=False)


def expire_licenses() -> int:
    """Approved providers past their licence date drop out of the marketplace."""
    return execute(
        "update providers set status = 'suspended', review_note = 'License expired', "
        f"updated_at = now() where status = 'approved' and license_expires_at < {TODAY}"
    )


def _purge_blockers(conn) -> list[str]:
    """Why the sample data can't be deleted: never take real money records or a real client's hire with it."""
    row = conn.execute(
        """
        select
          (select count(*) from payments pay join engagements e on e.id = pay.engagement_id
             where e.is_sample or e.provider_id in (select id from providers where is_sample)) as payments,
          (select count(*) from provider_ledger l where l.provider_id in (select id from providers where is_sample)) as ledger,
          (select count(*) from payouts po where po.provider_id in (select id from providers where is_sample)) as payouts,
          (select count(*) from engagements e where not e.is_sample
             and e.provider_id in (select id from providers where is_sample)) as real_hires
        """
    ).fetchone()
    reasons = []
    if row["payments"]:
        reasons.append(f"{row['payments']} payment(s)")
    if row["ledger"]:
        reasons.append(f"{row['ledger']} earnings record(s)")
    if row["payouts"]:
        reasons.append(f"{row['payouts']} payout(s)")
    if row["real_hires"]:
        reasons.append(f"{row['real_hires']} hire(s) from real clients")
    return reasons


def sample_status() -> dict:
    """What the "Remove sample data" button may do here."""
    from config.config import settings

    count = fetch_one("select count(*) as c from providers where is_sample")["c"]
    if settings.environment.lower() in ("production", "prod"):
        return {"providers": count, "can_purge": False, "reason": "Sample data can't be removed on the live site."}
    with connection() as conn:
        blockers = _purge_blockers(conn)
    reason = ("Sample providers are linked to " + ", ".join(blockers) + ". Remove those links first."
              if blockers else None if count else "There is no sample data.")
    return {"providers": count, "can_purge": bool(count) and not blockers, "reason": reason}


def purge_samples(*, actor: str) -> dict:
    """Delete the demo providers, hires and reviews from scripts/seed_providers.py. Only outside production,
    and never when a sample provider has money records or a real client's hire."""
    from config.config import settings

    if settings.environment.lower() in ("production", "prod"):
        raise MarketplaceError("Sample data can't be removed on the live site", 403)
    with connection() as conn, conn.transaction():
        # Lock the sample providers so no hire or payment attaches to them while we check
        conn.execute("select id from providers where is_sample for update").fetchall()
        blockers = _purge_blockers(conn)
        if blockers:
            raise MarketplaceError("Not removed: sample providers are linked to " + ", ".join(blockers), 409)
        users = conn.execute(
            "select user_id::text from providers where is_sample and user_id is not null"
        ).fetchall()
        hires = conn.execute("delete from engagements where is_sample returning id").fetchall()
        n = conn.execute("delete from providers where is_sample returning id").fetchall()
        conn.execute(
            "delete from users where id = any(%s::uuid[]) "
            "and (email like '%%@sample.invalid' or email like '%%.sample@example.com')",
            ([u["user_id"] for u in users],),
        )
        conn.execute("delete from users where email like 'sample-client-%%@sample.invalid'")
    log.warning("Sample data removed by %s: %s providers, %s hires", actor, len(n), len(hires))
    return {"providers_removed": len(n), "hires_removed": len(hires)}
