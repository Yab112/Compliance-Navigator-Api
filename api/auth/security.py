"""Primitives: password hashing, access-token JWTs, opaque random tokens."""

from __future__ import annotations

import hashlib
import re
import secrets
import time

import bcrypt
import jwt
from jwt import PyJWTError

from config.config import settings

ISSUER = "compliance-navigator"
# bcrypt only looks at the first 72 bytes, longer passwords are rejected, not silently truncated
MAX_PASSWORD_BYTES = 72
# Compared against when the email is unknown so both paths cost one bcrypt check
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt()).decode()


def password_problem(password: str) -> str | None:
    """Why a new password is unacceptable, or None."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        return "Password is too long (max 72 bytes)"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number"
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(password: str, password_hash: str | None) -> bool:
    encoded = password.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        bcrypt.checkpw(b"x", _DUMMY_HASH.encode())
        return False
    return bcrypt.checkpw(encoded, (password_hash or _DUMMY_HASH).encode()) and bool(password_hash)


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_access_token(user_id: str, session_id: str, role: str) -> tuple[str, int]:
    ttl = settings.access_token_ttl_minutes * 60
    now = int(time.time())
    token = jwt.encode(
        {"sub": user_id, "sid": session_id, "role": role, "iss": ISSUER, "iat": now, "exp": now + ttl},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return token, ttl


def decode_access_token(token: str) -> dict | None:
    try:
        claims = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            issuer=ISSUER,
            options={"require": ["sub", "sid", "exp", "iat"]},
        )
    except PyJWTError:
        return None
    return claims
