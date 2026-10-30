"""Agency teams: members, join requests and invitations."""

from __future__ import annotations

from services.db import connection, fetch_all, fetch_one

from .common import LIVE, PRIVATE_COLUMNS, MarketplaceError, _log, get_for_user
from .trust import recompute

# ---------------------------------------------------------------- agency teams


def team(agency_id: str, include_pending: bool = False) -> list[dict]:
    statuses = ("active", "pending") if include_pending else ("active",)
    return fetch_all(
        """
        select m.id::text as membership_id, m.status, m.initiated_by, m.role_title,
          p.id::text, p.slug, p.display_name, p.photo_url, p.headline, p.trust_score,
          p.rating_avg::float, p.rating_count, p.completed_count, p.national_id_verified as id_verified
        from provider_members m left join providers p on p.id = m.member_id
        where m.agency_id = %s and m.status = any(%s)
        order by m.status, p.trust_score desc nulls last
        """,
        (agency_id, list(statuses)),
    )


def agency_of(provider_id: str, include_pending: bool = False) -> dict | None:
    statuses = ("active", "pending") if include_pending else ("active",)
    return fetch_one(
        """
        select m.id::text as membership_id, m.status, m.initiated_by, a.id::text, a.slug,
          a.display_name, a.photo_url, a.trust_score
        from provider_members m join providers a on a.id = m.agency_id
        where m.member_id = %s and m.status = any(%s)
        order by m.created_at desc limit 1
        """,
        (provider_id, list(statuses)),
    )


def _agency_by_slug(slug: str) -> dict:
    agency = fetch_one(
        f"select {PRIVATE_COLUMNS} from providers p where p.slug = %s or p.id::text = %s", (slug, slug)
    )
    if not agency or agency["provider_type"] != "agency":
        raise MarketplaceError("Agency not found", 404)
    return agency


def request_to_join(user_id: str, agency_slug: str, actor: str) -> dict:
    me = get_for_user(user_id)
    if not me or me["entity_type"] != "individual" or me["provider_type"] == "agency":
        raise MarketplaceError("Only individual Guday Geday agents can join an agency", 403)
    agency = _agency_by_slug(agency_slug)
    if agency["status"] != "approved":
        raise MarketplaceError("This agency isn't active", 409)
    if agency_of(me["id"], include_pending=True):
        raise MarketplaceError("You already belong to, or asked to join, an agency", 409)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "insert into provider_members (agency_id, member_id, initiated_by) values (%s, %s, 'member') "
            "returning id::text",
            (agency["id"], me["id"]),
        ).fetchone()
        _log(conn, agency["id"], "member_requested", actor, me["display_name"])
    return {"membership_id": row["id"]}


def invite_member(user_id: str, member_slug: str, role_title: str | None, actor: str) -> dict:
    agency = get_for_user(user_id)
    if not agency or agency["provider_type"] != "agency":
        raise MarketplaceError("Only agencies can invite members", 403)
    if agency["status"] != "approved":
        raise MarketplaceError("Your agency can invite members once it is approved", 409)
    # Only listed agents: a pending or suspended profile can't be tied up by an invitation
    member = fetch_one(f"select p.id::text, p.entity_type, p.provider_type, p.display_name from providers p "
                       f"where (p.slug = %s or p.id::text = %s) and {LIVE}", (member_slug, member_slug))
    if not member or member["entity_type"] != "individual" or member["provider_type"] == "agency":
        raise MarketplaceError("Provider not found. Members must be individual Guday Geday agents.", 404)
    if agency_of(member["id"], include_pending=True):
        raise MarketplaceError("That provider already belongs to, or asked to join, an agency", 409)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "insert into provider_members (agency_id, member_id, initiated_by, role_title) "
            "values (%s, %s, 'agency', %s) returning id::text",
            (agency["id"], member["id"], role_title),
        ).fetchone()
        _log(conn, agency["id"], "member_invited", actor, member["display_name"])
    return {"membership_id": row["id"]}


def respond_membership(user_id: str, membership_id: str, action: str, actor: str) -> dict:
    """The side that didn't start the request accepts or declines; either side can remove."""
    me = get_for_user(user_id)
    m = fetch_one(
        "select id::text, agency_id::text, member_id::text, initiated_by, status from provider_members where id::text = %s",
        (membership_id,),
    )
    if not me or not m or me["id"] not in (m["agency_id"], m["member_id"]):
        raise MarketplaceError("Membership not found", 404)
    i_am_agency = me["id"] == m["agency_id"]
    if action in ("accept", "decline"):
        if m["status"] != "pending":
            raise MarketplaceError("This request was already answered", 409)
        responder_is_agency = m["initiated_by"] == "member"
        if i_am_agency != responder_is_agency:
            raise MarketplaceError("Waiting for the other side to respond", 403)
        new_status = "active" if action == "accept" else "declined"
    elif action == "remove":
        if m["status"] not in ("active", "pending"):
            raise MarketplaceError("Nothing to remove", 409)
        new_status = "removed"
    else:
        raise MarketplaceError("Unknown action")
    with connection() as conn, conn.transaction():
        conn.execute(
            "update provider_members set status = %s, responded_at = now() where id = %s",
            (new_status, membership_id),
        )
        _log(conn, m["agency_id"], f"member_{new_status}", actor)
    recompute(m["agency_id"])
    return {"status": new_status}
