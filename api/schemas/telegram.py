"""Telegram usernames, as people type them: "@meron", "t.me/meron" or "https://t.me/meron"."""

import re
from typing import Annotated

from pydantic import AfterValidator

# Telegram's own rule: 5 to 32 characters, letters, digits and underscores, starting with a letter
_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def clean_telegram(value: str | None) -> str | None:
    if value is None:
        return None
    v = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", value.strip(), flags=re.I).lstrip("@").strip("/")
    if not v:
        return None
    if not _USERNAME.match(v):
        raise ValueError("Enter your Telegram username, for example @meron_tadesse (5 to 32 letters, digits or _)")
    return v


TelegramUsername = Annotated[str | None, AfterValidator(clean_telegram)]
