"""Errors and the small value types shared by the auth modules."""

from __future__ import annotations

from dataclasses import dataclass


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ClientInfo:
    ip: str | None = None
    user_agent: str | None = None


@dataclass
class Email:
    to: str
    subject: str
    text: str


@dataclass
class SessionTokens:
    user: dict
    access_token: str
    expires_in: int
    refresh_token: str | None  # None when the browser already holds the current cookie
