"""Encrypt small secrets at rest (e.g. a provider's bank account number for payouts).

Key: PAYOUT_ENCRYPTION_KEY if set (a Fernet key), else derived from SECRET_KEY. Changing either
makes stored values unreadable, so set it once per environment.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from config.config import settings


def _fernet() -> MultiFernet:
    """
    PAYOUT_ENCRYPTION_KEY may list several keys, newest first: new values use the first, and older ones can
    still be read, so keys can be rotated. Without it (development only; production refuses to start) the key
    comes from SECRET_KEY, which is also how values saved before the setting existed are read.
    """
    keys = [k.strip() for k in (settings.payout_encryption_key or "").split(",") if k.strip()]
    keys.append(base64.urlsafe_b64encode(hashlib.sha256(f"payout:{settings.secret_key}".encode()).digest()).decode())
    return MultiFernet([Fernet(k) for k in keys])


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
