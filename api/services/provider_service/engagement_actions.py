"""What the provider and the client do to a hire as it moves along."""

from __future__ import annotations

from services import provider_service
from services.db import connection, execute, fetch_one

from .common import LIVE, MarketplaceError, get_for_user
from .engagements import _event, _payments_on, _tell
from .readiness import not_ready_message
from .trust import recompute

CHANGED_MEANWHILE = "This job changed in the meantime. Refresh the page and try again."


def _set_status(engagement_id: str, status: str, extra: str = "", params: tuple = (), *,
                allowed: tuple[str, ...] | set[str], guard: str = "", guard_params: tuple = (),
                who: str, action: str, actor: str | None = None, note: str | None = None) -> str:
    """Move a hire only if it is still in an allowed status (and passes the guard), in one statement, so two
    people acting at once can't both win (cancel against pay, start against decline). Records the change in
    the hire's history. Returns the status it moved from; raises 409 when the hire had already moved on."""
    with connection() as conn, conn.transaction():
        row = conn.execute(
            f"update engagements e set status = %s, updated_at = now() {extra} "
            f"from engagements o where o.id = e.id and e.id = %s and e.status = any(%s) {guard} "
            f"returning o.status as old_status, e.provider_id::text",
            (status, *params, engagement_id, list(allowed), *guard_params),
        ).fetchone()
        if not row:
            raise MarketplaceError(CHANGED_MEANWHILE, 409)
        _event(conn, engagement_id, action, who=who, actor=actor, from_status=row["old_status"], to_status=status,
               note=note, provider_id=row["provider_id"])
    return row["old_status"]


def _save_price(engagement_id: str, price: float, note: str | None) -> None:
    # Never once the client is paying or has paid, even if a checkout started a moment ago
    changed = execute(
        "update engagements set agreed_price = %s, price_note = %s, updated_at = now() where id = %s "
        "and status in ('accepted', 'in_progress') and payment_status not in ('paid', 'pending')",
        (price, (note or "").strip() or None, engagement_id),
    )
    if not changed:
        raise MarketplaceError("The price can't change now: the client already paid or is paying", 409)


def provider_action(engagement_id: str, *, user_id: str, action: str, reason: str | None = None,
                    price: float | None = None, price_note: str | None = None, note: str | None = None) -> dict:
    """Providers move their own jobs forward: requested → accepted → in_progress → completed."""
    me = get_for_user(user_id)
    eng = provider_service.get_engagement(engagement_id)
    if not me or not eng or eng["provider_id"] != me["id"]:
        raise MarketplaceError("Job not found", 404)
    if me["status"] != "approved":
        raise MarketplaceError("Your profile is not active", 403)
    moves = {
        "accept": ({"requested"}, "accepted", ", accepted_at = now()"),
        "decline": ({"requested"}, "declined", ", declined_reason = %s"),
        "start": ({"accepted"}, "in_progress", ""),
        # Delivered: the client then confirms, or it closes on its own after AUTO_CONFIRM_DAYS
        # Delivered: this also asks the client to pay; paying closes the job
        "complete": ({"in_progress"}, "completed", ", completed_at = now(), completion_note = %s, payment_requested_at = now()"),
    }
    if action == "set_price":
        if price is None or price <= 0:
            raise MarketplaceError("Enter the price in birr")
        # The price can change until the work is delivered; after that it is the amount the client pays
        if eng["status"] not in ("accepted", "in_progress"):
            raise MarketplaceError("Accept the job first" if eng["status"] == "requested"
                                   else "The price can't change once the work is delivered", 409)
        if eng["payment_status"] in ("paid", "pending"):
            raise MarketplaceError("The client already paid or is paying; the price can't change now", 409)
        _save_price(engagement_id, price, price_note)
        _tell(eng, "client", f"{me['display_name']} changed the price to {price:,.0f} ETB",
              price_note or "You pay once the work is delivered.")
        return provider_service.get_engagement(engagement_id)
    if action not in moves:
        raise MarketplaceError("Unknown action")
    allowed, new_status, extra = moves[action]
    if eng["status"] not in allowed:
        raise MarketplaceError(f"Can't {action} a job that is {eng['status'].replace('_', ' ')}", 409)
    if action in ("accept", "start") and not fetch_one(f"select 1 from providers p where p.id = %s and {LIVE}",
                                                       (me["id"],)):
        # New work needs every rule to hold (vetting, agreement, profile). Work already started can still be
        # delivered and paid for, and a request can still be declined, so clients and earnings are not stuck.
        raise MarketplaceError("You can't take on new work until you are ready to work again: "
                               f"{not_ready_message(me)}. See your dashboard for what to fix.", 409)
    if action == "accept" and _payments_on() and not price:
        raise MarketplaceError("Set your price when you accept: the client pays it once you deliver")
    if action == "complete":
        if len((note or "").strip()) < 10:
            raise MarketplaceError("Tell the client what you delivered (at least a sentence)")
        if _payments_on() and not eng.get("agreed_price"):
            raise MarketplaceError("Set your price before delivering", 409)
    params = (reason,) if action == "decline" else ((note or "").strip()[:2000],) if action == "complete" else ()
    if action == "complete" and eng.get("payment_status") == "paid":
        # Paid before delivery (the old order): delivering closes it, there is nothing left to pay
        extra += ", client_confirmed_at = now()"
    # Still this provider's job (staff may have reassigned it a moment ago) and still in the expected status
    _set_status(engagement_id, new_status, extra, params, allowed=tuple(allowed), guard="and e.provider_id = %s",
                guard_params=(me["id"],), who="provider", action=action, actor=me["display_name"],
                note=reason if action == "decline" else note if action == "complete" else None)
    if action == "accept" and price:
        _save_price(engagement_id, price, price_note)
    recompute(me["id"])
    name = me["display_name"]
    messages = {
        "accept": (f"{name} accepted your request",
                   (f"Price: {price:,.0f} ETB, paid once the work is delivered. " if price else "")
                   + "Their phone and Telegram are now on your request."),
        "decline": (f"{name} declined your request", reason or "You can choose another verified provider."),
        "start": (f"{name} started work on {eng['title']}", None),
        "complete": (f"{name} delivered {eng['title']}: please pay",
                     f"\"{(note or '').strip()[:120]}\" Pay {float(eng.get('agreed_price') or 0):,.0f} ETB to close the job, "
                     "or report a problem."),
    }
    _tell(eng, "client", *messages[action])
    return provider_service.get_engagement(engagement_id)


def client_action(engagement_id: str, *, user_id: str, action: str, reason: str | None = None) -> dict:
    eng = provider_service.get_engagement(engagement_id)
    if not eng or eng["client_user_id"] != user_id:
        raise MarketplaceError("Request not found", 404)
    if action == "cancel":
        if eng.get("payment_status") in ("paid", "pending"):
            raise MarketplaceError("This job is paid. If something is wrong, report a problem and our team will "
                                   "sort it out.", 409)
        if eng["status"] == "completed":
            raise MarketplaceError("The work is delivered. Pay to close the job, or report a problem if it isn't right.", 409)
        if eng["status"] not in ("open", "requested", "accepted", "in_progress"):
            raise MarketplaceError("This request can't be cancelled now", 409)
        # The payment guard is in the statement itself: a checkout that started a moment ago wins
        _set_status(engagement_id, "cancelled", allowed=("open", "requested", "accepted", "in_progress"),
                    guard="and e.payment_status not in ('paid', 'pending')", who="client", action="cancel")
    elif action == "complete":
        # Without online payment the client confirms delivery; with it, paying is the confirmation
        if _payments_on():
            raise MarketplaceError("Pay for the delivered work to close the job", 409)
        if eng["status"] != "completed":
            who = eng.get("provider_name") or "The provider"
            raise MarketplaceError(f"You can confirm once {who} marks the work as delivered", 409)
        if eng.get("client_confirmed_at"):
            raise MarketplaceError("You already confirmed this job", 409)
        with connection() as conn, conn.transaction():
            done = conn.execute("update engagements set client_confirmed_at = now(), updated_at = now() "
                                "where id = %s and status = 'completed' and client_confirmed_at is null returning id",
                                (engagement_id,)).fetchone()
            if not done:
                raise MarketplaceError(CHANGED_MEANWHILE, 409)
            _event(conn, engagement_id, "confirmed", who="client", from_status="completed", to_status="completed",
                   provider_id=eng["provider_id"])
    elif action == "dispute":
        if eng["status"] not in ("accepted", "in_progress", "completed"):
            raise MarketplaceError("You can report a problem once a provider has taken the job", 409)
        if eng["disputed"]:
            raise MarketplaceError("You already reported a problem with this job", 409)
        if not reason:
            raise MarketplaceError("Tell us what went wrong")
        with connection() as conn, conn.transaction():
            done = conn.execute(
                "update engagements set disputed = true, dispute_status = 'open', dispute_reason = %s, updated_at = now() "
                "where id = %s and not coalesce(disputed, false) "
                "and status in ('accepted', 'in_progress', 'completed') returning status",
                (reason, engagement_id),
            ).fetchone()
            if not done:
                raise MarketplaceError(CHANGED_MEANWHILE, 409)
            _event(conn, engagement_id, "complaint", who="client", from_status=done["status"], to_status=done["status"],
                   note=reason, provider_id=eng["provider_id"])
    else:
        raise MarketplaceError("Unknown action")
    if eng["provider_id"]:
        recompute(eng["provider_id"])
        first = (eng["client_name"] or "The client").split()[0]
        messages = {
            "cancel": (f"Request cancelled: {eng['title']}", f"{first} cancelled this request."),
            "complete": (f"{first} confirmed {eng['title']} is done", "The job is closed and counts toward your Job Success."),
            "dispute": (f"A client reported a problem with {eng['title']}", "Our staff will look at it and contact you."),
        }
        _tell(eng, "provider", *messages[action])
    return provider_service.get_engagement(engagement_id)
