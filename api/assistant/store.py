"""Conversation state, transcript and the NLU learning log in Postgres."""

from __future__ import annotations

from services.db import Jsonb, execute, fetch_all, fetch_one

from assistant.entities import redact


def create(user_id: str | None, language: str, state: dict) -> dict:
    return fetch_one(
        """
        insert into assistant_conversations (user_id, language, state) values (%s, %s, %s)
        returning id::text, user_id::text, language, state
        """,
        (user_id, language, Jsonb(state)),
    )


def get(conversation_id: str, user_id: str | None) -> dict | None:
    """Anonymous conversations are reachable by their (unguessable) id; signed-in ones only by their owner."""
    try:
        row = fetch_one(
            "select id::text, user_id::text, language, state from assistant_conversations where id = %s",
            (conversation_id,),
        )
    except Exception:  # malformed id
        return None
    if not row:
        return None
    if row["user_id"] and row["user_id"] != user_id:
        return None
    if not row["user_id"] and user_id:
        # Signing in mid-conversation claims it
        execute("update assistant_conversations set user_id = %s where id = %s", (user_id, conversation_id))
    return row


def save_state(conversation_id: str, language: str, state: dict) -> None:
    execute(
        "update assistant_conversations set state = %s, language = %s, updated_at = now() where id = %s",
        (Jsonb(state), language, conversation_id),
    )


def add_message(conversation_id: str, role: str, content: str, payload: dict | None = None) -> None:
    execute(
        "insert into assistant_messages (conversation_id, role, content, payload) values (%s, %s, %s, %s)",
        (conversation_id, role, redact(content), Jsonb(payload) if payload is not None else None),
    )


def history(conversation_id: str, limit: int = 100, after: int | None = None) -> list[dict]:
    return fetch_all(
        """
        select id, role, content, payload, created_at from assistant_messages
        where conversation_id = %s and id > %s order by id desc limit %s
        """,
        (conversation_id, after or 0, limit),
    )[::-1]


def log_turn(conversation_id: str, message: str, language: str, intent: str | None, confidence: float | None,
             ranked: list | None, resolved_service: str | None, model_version: str | None) -> None:
    execute(
        """
        insert into assistant_turns
          (conversation_id, message_redacted, language, intent, confidence, ranked, resolved_service, model_version)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (conversation_id, redact(message)[:500], language, intent, confidence,
         Jsonb(ranked) if ranked is not None else None, resolved_service, model_version),
    )


def turns_to_review(max_confidence: float, limit: int, include_labelled: bool = False) -> list[dict]:
    labelled = "" if include_labelled else "and labelled_intent is null"
    return fetch_all(
        f"""
        select id, message_redacted, language, intent, confidence, ranked, resolved_service, model_version,
               labelled_intent, labelled_service, labelled_by, labelled_at, created_at
        from assistant_turns
        where (confidence is null or confidence < %s) {labelled}
        order by created_at desc limit %s
        """,
        (max_confidence, limit),
    )


def label_turn(turn_id: int, intent: str | None, service: str | None, actor: str) -> dict | None:
    return fetch_one(
        """
        update assistant_turns set labelled_intent = %s, labelled_service = %s, labelled_by = %s, labelled_at = now()
        where id = %s returning id, labelled_intent, labelled_service
        """,
        (intent, service, actor, turn_id),
    )


def turn_stats() -> dict:
    return fetch_one(
        """
        select count(*) as turns,
               count(*) filter (where created_at > now() - interval '7 days') as turns_7d,
               count(*) filter (where confidence < 0.5) as low_confidence,
               count(*) filter (where labelled_intent is not null) as labelled,
               count(distinct conversation_id) as conversations
        from assistant_turns
        """
    )
