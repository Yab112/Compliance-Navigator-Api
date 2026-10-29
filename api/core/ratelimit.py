"""A small shared rate limiter backed by Postgres, so every API worker sees the same counts.

Each bucket has one or more rules ("at most N in S seconds"), counted in fixed windows. The key is the
signed-in user's id when there is one, otherwise the client IP. The IP is `request.client.host`, which
uvicorn rewrites from X-Forwarded-For only when the request comes from a proxy listed in
FORWARDED_ALLOW_IPS (see main.py), so it can't be spoofed by the caller.

Use it as a route dependency:  `dependencies=[Depends(limit("assistant"))]`
or call `check(bucket, key)` inside a route. Blocked calls get 429 with a Retry-After header.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from core.deps import bearer_scheme, get_optional_user
from services.db import execute, fetch_one

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rule:
    limit: int
    seconds: int


MINUTE, HOUR, DAY = 60, 3600, 86400

RULES: dict[str, tuple[Rule, ...]] = {
    # Per network: stops mail bombing and link churn. Per email: extra requests are silently not sent
    "forgot_password": (Rule(10, HOUR),),
    "forgot_password_email": (Rule(3, HOUR),),
    "verify_resend": (Rule(3, HOUR), Rule(10, DAY)),
    # Anonymous and signed-in conversations call the language model, which costs money per turn
    "assistant": (Rule(20, MINUTE), Rule(300, DAY)),
    "chat": (Rule(10, MINUTE), Rule(150, DAY)),
    "transcribe": (Rule(6, MINUTE), Rule(60, DAY)),
    # Each new request rings a provider's bell
    "hire_create": (Rule(10, HOUR), Rule(30, DAY)),
    "review_create": (Rule(10, HOUR), Rule(30, DAY)),
    # Each webhook call makes an outbound check with Chapa
    "chapa_webhook": (Rule(5, MINUTE),),
}

# Tests switch this off so hundreds of calls from one "IP" are not refused
ENABLED = True


class RateLimited(HTTPException):
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a little and try again.",
            headers={"Retry-After": str(max(1, retry_after))},
        )


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def hit(bucket: str, key: str, rules: tuple[Rule, ...] | None = None) -> int | None:
    """Count one attempt. Returns the seconds to wait when any rule is over its limit, else None."""
    if not ENABLED:
        return None
    rules = rules if rules is not None else RULES[bucket]
    wait = None
    for rule in rules:
        row = fetch_one(
            """
            with w as (
              select to_timestamp(floor(extract(epoch from now()) / %(s)s) * %(s)s) as start
            )
            insert into rate_limit_counters (bucket, key, window_start, hits)
            select %(b)s, %(k)s, w.start, 1 from w
            on conflict (bucket, key, window_start) do update set hits = rate_limit_counters.hits + 1
            returning hits,
              ceil(extract(epoch from (window_start + make_interval(secs => %(s)s) - now())))::int as retry_after
            """,
            {"b": f"{bucket}/{rule.seconds}", "k": key[:200], "s": rule.seconds},
        )
        if row["hits"] > rule.limit:
            wait = max(wait or 0, row["retry_after"])
    if random.random() < 0.01:
        execute("delete from rate_limit_counters where window_start < now() - interval '2 days'")
    if wait is not None:
        log.info("Rate limit %s reached for %s", bucket, key[:40])
    return wait


def check(bucket: str, key: str, rules: tuple[Rule, ...] | None = None) -> None:
    """Count one attempt and raise 429 when over the limit."""
    wait = hit(bucket, key, rules)
    if wait is not None:
        raise RateLimited(wait)


def key_for(request: Request, user_id: str | None) -> str:
    return f"user:{user_id}" if user_id else f"ip:{client_ip(request) or 'unknown'}"


def limit(bucket: str):
    """A route dependency: count the call against the signed-in user, or the IP when signed out."""
    if bucket not in RULES:
        raise KeyError(bucket)

    def dependency(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    ) -> None:
        user = get_optional_user(credentials) if credentials else None
        check(bucket, key_for(request, user.id if user else None))

    return dependency


def once(bucket: str, key: str, ttl_seconds: int) -> bool:
    """True the first time `key` is seen in `bucket` within `ttl_seconds`; False for a repeat."""
    execute("delete from once_keys where bucket = %s and expires_at < now()", (bucket,))
    row = fetch_one(
        """
        insert into once_keys (bucket, key, expires_at)
        values (%s, %s, now() + make_interval(secs => %s))
        on conflict (bucket, key) do nothing
        returning key
        """,
        (bucket, key[:200], ttl_seconds),
    )
    return row is not None


def forget(bucket: str, key: str) -> None:
    """Let `key` be used again (e.g. the work it guarded failed and should be retried)."""
    execute("delete from once_keys where bucket = %s and key = %s", (bucket, key[:200]))
