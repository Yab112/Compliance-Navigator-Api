"""Encrypt small secrets at rest (e.g. a provider's bank account number for payouts).

Key: PAYOUT_ENCRYPTION_KEY if set (a Fernet key), else derived from SECRET_KEY. Changing either
makes stored values unreadable, so set it once per environment.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from config.config import settings


def _fernet() -> Fernet:
    key = os.environ.get("PAYOUT_ENCRYPTION_KEY")
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(f"payout:{settings.secret_key}".encode()).digest()).decode()
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
