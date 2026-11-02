"""Reminders people asked for, delivered to their notification bell on the due date.

Render's free plan runs no background worker, so delivery happens in two places: when the person's
bell loads (deliver_due_for), and in the daily job for everyone (deliver_due) where a worker runs.
"""

from __future__ import annotations

from datetime import date, timedelta

from services import notifications
from services.db import connection, fetch_all, fetch_one

MAX_AHEAD_DAYS = 730
MAX_OPEN_PER_USER = 50


class ReminderError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def create(user_id: str, *, title: str, due_on: date, body: str | None = None, link: str | None = None,
           source: str = "assistant", conversation_id: str | None = None) -> dict:
    title, body = (title or "").strip(), (body or "").strip() or None
    if not 3 <= len(title) <= 200:
        raise ReminderError("Give the reminder a short title")
    today = date.today()
    if due_on < today or due_on > today + timedelta(days=MAX_AHEAD_DAYS):
        raise ReminderError("Pick a date between today and two years from now")
    if link and not link.startswith("/"):
        link = None  # our own pages only
    open_count = fetch_one("select count(*) as c from user_reminders where user_id = %s and delivered_at is null"
                           " and cancelled_at is null", (user_id,))["c"]
    if open_count >= MAX_OPEN_PER_USER:
        raise ReminderError("You have too many open reminders. Cancel some first.")
    row = fetch_one(
        "insert into user_reminders (user_id, title, body, due_on, link, source, conversation_id)"
        " values (%s, %s, %s, %s, %s, %s, %s) returning id::text, title, body, due_on, link, created_at",
        (user_id, title, (body or "")[:1000] or None, due_on, link, source, conversation_id))
    return row


def list_for(user_id: str) -> list[dict]:
    return fetch_all(
        "select id::text, title, body, due_on, link, source, created_at, delivered_at from user_reminders"
        " where user_id = %s and cancelled_at is null order by delivered_at is not null, due_on limit 100", (user_id,))


def cancel(user_id: str, reminder_id: str) -> bool:
    row = fetch_one("update user_reminders set cancelled_at = now() where id::text = %s and user_id = %s"
                    " and cancelled_at is null and delivered_at is null returning id", (reminder_id, user_id))
    return bool(row)


def _deliver(where: str, params: tuple) -> int:
    """Claim due reminders and put each on its owner's bell, once."""
    with connection() as conn, conn.transaction():
        due = conn.execute(
            f"update user_reminders set delivered_at = now() where id in (select id from user_reminders"
            f" where delivered_at is null and cancelled_at is null and due_on <= current_date {where}"
            " for update skip locked) returning user_id::text, title, body, link", params).fetchall()
    for r in due:
        notifications.notify([r["user_id"]], kind="reminder", title=f"Reminder: {r['title']}", body=r["body"],
                             link=r["link"])
    return len(due)


def deliver_due_for(user_id: str) -> int:
    return _deliver("and user_id = %s", (user_id,))


def deliver_due() -> int:
    return _deliver("", ())
