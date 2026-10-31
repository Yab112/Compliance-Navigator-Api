"""One SMTP sender for account and staff emails.

SMTP_SECURITY picks how the connection is protected:
- starttls (default, usually port 587): plain connect, then upgrade to TLS
- ssl (usually port 465): TLS from the first byte
- none: no TLS, only for a local mail catcher in development (production refuses it)
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from config.config import settings


def deliver(to: str, subject: str, body: str) -> None:
    """Send one plain-text email. Raises on any SMTP error; callers decide how to log it."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(body)
    mode = (settings.smtp_security or "starttls").strip().lower()
    if mode == "ssl":
        smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with smtp:
        if mode == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(msg)
