"""Accountability on both sides of a hire.

Client record: what a provider sees before taking a client's request (never public):
  hire rate      paid jobs / decided accepted requests; "decided" = paid, cancelled after the
                 provider accepted, or delivered but left unpaid (setting client_unpaid_days). Shown from
                 client_record_min decided requests; "New client" before that.
  paid jobs, cancellations after acceptance, rating from providers, member since.

Provider -> client ratings: one per closed job.
Review changes: a client can't edit a review; they request a change and staff approve it.
"""

from __future__ import annotations

from services import notifications
from services.db import connection, execute, fetch_all, fetch_one
from services import platform_settings



class ReputationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------- client record


def client_record(user_id: str | None) -> dict | None:
    if not user_id:
        return None
    jobs = fetch_one(
        f"""
        select count(*) filter (where payment_status = 'paid') as paid,
               count(*) filter (where status = 'cancelled' and accepted_at is not null) as cancelled_after_accept,
               count(*) filter (where status = 'completed' and payment_status <> 'paid' and client_confirmed_at is null
                                  and completed_at < now() - interval '{platform_settings.get_int("client_unpaid_days")} days') as left_unpaid,
               count(*) filter (where status = 'completed' and client_confirmed_at is not null) as closed
        from engagements where client_user_id = %s and provider_id is not null
        """,
        (user_id,),
    )
    ratings = fetch_one(
        "select count(*) as n, avg(rating)::float as avg from client_reviews where client_user_id = %s and not hidden",
        (user_id,),
    )
    member = fetch_one("select created_at from users where id = %s", (user_id,))
    decided = jobs["paid"] + jobs["cancelled_after_accept"] + jobs["left_unpaid"]
    return {
        "paid_jobs": jobs["paid"],
        "closed_jobs": jobs["closed"],
        "cancelled_after_accept": jobs["cancelled_after_accept"],
        "left_unpaid": jobs["left_unpaid"],
        "decided": decided,
        "hire_rate": round(100 * jobs["paid"] / decided) if decided >= platform_settings.get_int("client_record_min") else None,
        "rating_avg": round(ratings["avg"], 1) if ratings["n"] else None,
        "rating_count": ratings["n"],
        "member_since": member["created_at"] if member else None,
    }


# ---------------------------------------------------------------- provider rates client


def rate_client(engagement_id: str, *, user_id: str, rating: int, comment: str | None) -> dict:
    from services import provider_service

    me = provider_service.get_for_user(user_id)
    eng = provider_service.get_engagement(engagement_id)
    if not me or not eng or eng["provider_id"] != me["id"]:
        raise ReputationError("Job not found", 404)
    if eng["status"] != "completed" or not eng.get("client_confirmed_at"):
        raise ReputationError("You can rate the client once the job is closed", 409)
    if fetch_one("select 1 from client_reviews where engagement_id = %s", (engagement_id,)):
        raise ReputationError("You already rated this client", 409)
    execute(
        "insert into client_reviews (engagement_id, provider_id, client_user_id, rating, comment) values (%s, %s, %s, %s, %s)",
        (engagement_id, me["id"], eng["client_user_id"], rating, (comment or "").strip()[:1000] or None),
    )
    return provider_service.get_engagement(engagement_id)


# ---------------------------------------------------------------- review change requests

CHANGE_COLUMNS = """
  c.id::text, c.review_id::text, c.old_rating, c.old_comment, c.new_rating, c.new_comment, c.reason, c.status,
  c.decided_by, c.decision_note, c.decided_at, c.created_at,
  e.id::text as engagement_id, e.title as job_title, e.client_name, p.display_name as provider_name, p.slug as provider_slug
"""
CHANGE_FROM = ("review_change_requests c join reviews r on r.id = c.review_id "
               "join engagements e on e.id = r.engagement_id join providers p on p.id = r.provider_id")


def request_change(engagement_id: str, *, user_id: str, rating: int, comment: str | None, reason: str) -> dict:
    review = fetch_one(
        "select r.id::text, r.rating, r.comment from reviews r join engagements e on e.id = r.engagement_id "
        "where r.engagement_id = %s and e.client_user_id = %s",
        (engagement_id, user_id),
    )
    if not review:
        raise ReputationError("You haven't reviewed this job", 404)
    if fetch_one("select 1 from review_change_requests where review_id = %s and status = 'pending'", (review["id"],)):
        raise ReputationError("A change for this review is already waiting for our team", 409)
    comment = (comment or "").strip()[:2000] or None
    if rating == review["rating"] and comment == review["comment"]:
        raise ReputationError("That is the same as your current review")
    execute(
        """
        insert into review_change_requests (review_id, requested_by, old_rating, old_comment, new_rating, new_comment, reason)
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        (review["id"], user_id, review["rating"], review["comment"], rating, comment, reason.strip()[:1000]),
    )
    admins = [r["id"] for r in fetch_all("select id::text from users where role = 'admin' and is_active")]
    notifications.notify(admins, kind="review_change", title="A client asked to change a review",
                         body=reason.strip()[:140], link="/admin/marketplace/reviews?tab=changes")
    return pending_change(review["id"])


def pending_change(review_id: str) -> dict | None:
    return fetch_one(f"select {CHANGE_COLUMNS} from {CHANGE_FROM} where c.review_id = %s and c.status = 'pending'", (review_id,))


def list_changes(status: str = "pending", limit: int = 25, offset: int = 0) -> dict:
    # The waiting queue is worked oldest first; decided ones are history, newest first
    order = "c.created_at" if status == "pending" else "coalesce(c.decided_at, c.created_at) desc"
    items = fetch_all(f"select {CHANGE_COLUMNS} from {CHANGE_FROM} where c.status = %s order by {order} limit %s offset %s",
                      (status, limit, offset))
    total = fetch_one("select count(*) as c from review_change_requests where status = %s", (status,))["c"]
    pending = fetch_one("select count(*) as c from review_change_requests where status = 'pending'")["c"]
    return {"total": total, "pending": pending, "items": items}


def decide_change(change_id: str, *, approve: bool, note: str | None, actor: str) -> dict:
    from services import provider_service

    with connection() as conn, conn.transaction():
        change = conn.execute(
            "update review_change_requests set status = %s, decided_by = %s, decision_note = %s, decided_at = now() "
            "where id = %s and status = 'pending' returning review_id::text, new_rating, new_comment, requested_by::text",
            ("approved" if approve else "rejected", actor, (note or "").strip() or None, change_id),
        ).fetchone()
        if not change:
            raise ReputationError("This request was already decided or doesn't exist", 409)
        if approve:
            conn.execute("update reviews set rating = %s, comment = %s, edited_at = now() where id = %s",
                         (change["new_rating"], change["new_comment"], change["review_id"]))
    review = fetch_one("select provider_id::text, engagement_id::text from reviews where id = %s", (change["review_id"],))
    eng = provider_service.get_engagement(review["engagement_id"])
    if approve:
        provider_service.recompute(review["provider_id"])
        provider_service._tell(eng, "provider", f"A review of {eng['title']} was updated",
                               f"Approved by our team. New rating: {change['new_rating']} stars.")
    title = "Your review change was approved" if approve else "Your review change was not approved"
    notifications.notify([change["requested_by"]], kind="review_change", title=title,
                         body=(note or "").strip()[:140] or None, link="/account/requests?tab=history")
    return fetch_one(f"select {CHANGE_COLUMNS} from {CHANGE_FROM} where c.id = %s", (change_id,))
