"""
Backend steps for the end-to-end suite that have no screen of their own.

The suite pipes this file to the API's Python (`python - <command> '<json>'`), with the working
directory set to api/ (or inside the API container), so it imports the app like the scripts do.
It prints one JSON line. Everything it creates uses the e2e-suite- prefix so cleanup can find it.

Commands
  provider         a ready sample provider: {slug, provider_id, user_id, display_name} or {}
  provider-action  {hire, action, price?, note?}: the provider moves the job (sample accounts can't sign in)
  notify           {email, title, body?}: one bell notification for that account
  cleanup          {emails?: [...]}: delete what those accounts (default: every e2e-suite- account) left behind
  clear-local-limits  forget the forgot-password rate count for loopback addresses (not in production)
"""

from __future__ import annotations

import json
import sys

PREFIX = "e2e-suite-"


def _provider(_: dict) -> dict:
    from services.db import fetch_one

    row = fetch_one(
        "select id::text as provider_id, user_id::text, slug, display_name from providers "
        "where is_sample and status = 'approved' and ready_to_work and provider_type = 'guday_geday' "
        "order by (slug = 'meron-tadesse') desc, slug limit 1"
    )
    return row or {}


def _provider_action(args: dict) -> dict:
    from services import provider_service
    from services.provider_service.engagement_actions import provider_action

    eng = provider_service.get_engagement(args["hire"])
    if not eng:
        raise SystemExit("hire not found")
    from services.db import fetch_one

    owner = fetch_one("select user_id::text, is_sample from providers where id = %s", (eng["provider_id"],))
    if not owner or not owner["is_sample"]:
        raise SystemExit("provider-action is only for sample providers")
    kwargs = {k: args[k] for k in ("price", "note", "reason") if args.get(k) is not None}
    done = provider_action(args["hire"], user_id=owner["user_id"], action=args["action"], **kwargs)
    return {"status": done["status"], "payment_status": done.get("payment_status")}


def _notify(args: dict) -> dict:
    from services import notifications
    from services.db import fetch_one

    email = args["email"].lower()
    if not email.startswith(PREFIX):
        raise SystemExit("notify is only for e2e-suite accounts")
    user = fetch_one("select id::text from users where lower(email) = %s", (email,))
    if not user:
        raise SystemExit("no such account")
    notifications.notify([user["id"]], kind="e2e", title=args["title"], body=args.get("body"))
    return {"user_id": user["id"]}


def _cleanup(args: dict) -> dict:
    from services.db import execute, fetch_all
    from services.provider_service.trust import recompute

    emails = [e.lower() for e in args.get("emails") or [] if e.lower().startswith(PREFIX)]
    # Without a list, every account the suite ever made (a crashed run leaves some behind)
    match = "lower(email) = any(%s)" if emails else "lower(email) like %s"
    param = emails if emails else PREFIX + "%"
    if args.get("emails") is not None and not emails:
        return {"users": 0, "staff": 0}

    users = [r["id"] for r in fetch_all(f"select id::text from users where {match}", (param,))]
    hires = [r["id"] for r in fetch_all("select id::text from engagements where client_user_id = any(%s::uuid[])", (users,))]
    providers = {r["provider_id"] for r in fetch_all(
        "select distinct provider_id::text from engagements where id = any(%s::uuid[]) and provider_id is not null",
        (hires,))}
    # The provider's bell heard about these hires; the titles carry the client name or the hire title
    execute("delete from notifications where title ilike %s or coalesce(body, '') ilike %s",
            ("%e2e suite%", "%e2e suite%"))
    # Hire titles read "e2e-suite: ...", so match without the trailing dash
    tag = "%" + PREFIX.rstrip("-") + "%"
    execute("delete from notifications where title ilike %s or coalesce(body, '') ilike %s", (tag, tag))
    execute("delete from provider_ledger where engagement_id = any(%s::uuid[])", (hires,))
    execute("delete from refunds where engagement_id = any(%s::uuid[])", (hires,))
    execute("delete from engagements where id = any(%s::uuid[])", (hires,))
    for uid in users:
        execute("delete from providers where user_id = %s", (uid,))
        execute("delete from organizations where created_by = %s", (uid,))
        execute("delete from roadmaps where user_id = %s", (uid,))
        execute("delete from user_consents where user_id = %s", (uid,))
    keys = users + [f"user:{u}" for u in users]
    execute("delete from rate_limit_counters where key = any(%s)", (keys,))
    execute(f"delete from auth_events where user_id = any(%s::uuid[]) or {match}", (users, param))
    execute("delete from users where id = any(%s::uuid[])", (users,))
    for pid in providers:
        recompute(pid)

    staff = [r["id"] for r in fetch_all(f"select id::text from staff_users where {match}", (param,))]
    staff_match = match.replace("email", "requested_by_email")
    execute(f"delete from approval_requests where {staff_match} or lower(coalesce(decided_by_email, '')) "
            + ("= any(%s)" if emails else "like %s"), (param, param))
    execute("update approval_requests set requested_by = null where requested_by = any(%s::uuid[])", (staff,))
    execute("update approval_requests set decided_by = null where decided_by = any(%s::uuid[])", (staff,))
    execute("delete from staff_audit_log where actor_id = any(%s::uuid[]) or lower(coalesce(actor_email, '')) "
            + ("= any(%s)" if emails else "like %s"), (staff, param))
    execute("delete from platform_settings_history where lower(changed_by) " + ("= any(%s)" if emails else "like %s"),
            (param,))
    execute("delete from staff_users where id = any(%s::uuid[])", (staff,))
    return {"users": len(users), "hires": len(hires), "staff": len(staff)}


def _clear_local_limits(_: dict) -> dict:
    """Forget the forgot-password count for this machine's address, so the suite can run more than a few
    times an hour. Only for loopback callers and never in production."""
    from config.config import settings
    from services.db import execute

    if settings.is_production:
        raise SystemExit("not in production")
    n = execute("delete from rate_limit_counters where bucket like 'forgot\\_password/%%' and key = any(%s)",
                (["ip:127.0.0.1", "ip:::1", "ip:localhost"],))
    return {"cleared": n}


COMMANDS = {"provider": _provider, "provider-action": _provider_action, "notify": _notify, "cleanup": _cleanup,
            "clear-local-limits": _clear_local_limits}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(f"usage: python - <{'|'.join(COMMANDS)}> '<json>'")
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(COMMANDS[sys.argv[1]](args), default=str))


if __name__ == "__main__":
    main()
