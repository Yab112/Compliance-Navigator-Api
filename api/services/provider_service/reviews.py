"""Client reviews of providers: leaving, replying and moderation."""

from __future__ import annotations

from services import provider_service
from services.db import connection, execute, fetch_all, fetch_one

from .common import MarketplaceError, _log, get_for_user
from .engagements import _payments_on, _tell
from .trust import recompute


def leave_review(engagement_id: str, *, user_id: str, data: dict) -> dict:
    eng = provider_service.get_engagement(engagement_id)
    if not eng or eng["client_user_id"] != user_id:
        raise MarketplaceError("Request not found", 404)
    if eng["status"] != "completed" or not eng.get("client_confirmed_at"):
        raise MarketplaceError("You can review once the job is closed: confirm the work is done first", 409)
    if not eng["provider_id"]:
        raise MarketplaceError("This job had no provider to review", 409)
    if _payments_on() and eng.get("payment_status") != "paid":
        raise MarketplaceError("Reviews are for jobs paid through Compliance Navigator", 409)
    if eng["review_id"]:
        raise MarketplaceError("You already reviewed this job", 409)
    execute(
        """
        insert into reviews (engagement_id, provider_id, client_user_id, rating, communication,
          fee_honesty, speed, outcome, would_hire_again, comment)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (engagement_id, eng["provider_id"], user_id, data["rating"], data.get("communication"),
         data.get("fee_honesty"), data.get("speed"), data.get("outcome"),
         data.get("would_hire_again"), data.get("comment")),
    )
    recompute(eng["provider_id"])
    _tell(eng, "provider", f"New {data['rating']}-star review for {eng['title']}", (data.get("comment") or "")[:140] or None)
    return provider_service.get_engagement(engagement_id)


def reply_to_review(review_id: str, *, user_id: str, reply: str) -> dict:
    me = get_for_user(user_id)
    review = fetch_one("select id::text, provider_id::text, reply from reviews where id::text = %s", (review_id,))
    if not me or not review or review["provider_id"] != me["id"]:
        raise MarketplaceError("Review not found", 404)
    if review["reply"]:
        raise MarketplaceError("You already replied to this review", 409)
    execute("update reviews set reply = %s, replied_at = now() where id = %s", (reply, review_id))
    return fetch_one("select id::text, reply, replied_at from reviews where id = %s", (review_id,))


def moderate_review(review_id: str, *, hide: bool, reason: str | None, actor: str) -> dict:
    review = fetch_one("select id::text, provider_id::text from reviews where id::text = %s", (review_id,))
    if not review:
        raise MarketplaceError("Review not found", 404)
    reason = (reason or "").strip() or None
    if hide and len(reason or "") < 5:
        raise MarketplaceError("Write why the review is hidden (at least 5 characters)")
    with connection() as conn, conn.transaction():
        conn.execute(
            "update reviews set hidden = %s, hidden_reason = %s, hidden_by = %s, "
            "hidden_at = case when %s then now() end where id = %s",
            (hide, reason if hide else None, actor if hide else None, hide, review_id),
        )
        _log(conn, review["provider_id"], "review_hidden" if hide else "review_restored", actor, reason)
    recompute(review["provider_id"])
    return {"id": review_id, "hidden": hide}


def list_reviews_admin(*, hidden: bool | None = None, max_rating: int | None = None, q: str | None = None,
                       limit: int = 50, offset: int = 0) -> dict:
    where, params = ["true"], []
    if q:
        where.append("(p.display_name ilike %s or u.email ilike %s or e.client_name ilike %s or r.comment ilike %s)")
        params += [f"%{q}%"] * 4
    if hidden is not None:
        where.append("r.hidden = %s")
        params.append(hidden)
    if max_rating:
        where.append("r.rating <= %s")
        params.append(max_rating)
    clause = " and ".join(where)
    joins = ("from reviews r join providers p on p.id = r.provider_id "
             "join engagements e on e.id = r.engagement_id left join users u on u.id = r.client_user_id")
    total = fetch_one(f"select count(*) as c {joins} where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select r.id::text, r.rating, r.comment, r.reply, r.hidden, r.hidden_reason, r.hidden_by,
          r.created_at, r.would_hire_again, p.display_name as provider_name, p.slug as provider_slug,
          u.email as client_email, e.title as job_title, e.id::text as engagement_id
        {joins}
        where {clause} order by r.created_at desc limit %s offset %s
        """,
        [*params, limit, offset],
    )
    return {"total": total, "items": items}
