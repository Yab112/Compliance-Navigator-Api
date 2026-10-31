"""SMTP connection security: starttls verifies the server, ssl uses implicit TLS, production refuses none."""

import smtplib

import pytest

from config.config import settings
from core import mailer


class FakeSMTP:
    instances: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.context, self.calls = host, port, context, []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.calls.append(("starttls", context))

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, msg):
        self.calls.append(("send", msg["To"]))


@pytest.fixture
def fake(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "u")
    return FakeSMTP


def test_starttls_verifies_the_server_certificate(fake, monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", "starttls")
    mailer.deliver("a@example.com", "Hi", "Body")
    smtp = fake.instances[0]
    kind, context = smtp.calls[0]
    assert kind == "starttls" and context is not None and context.check_hostname
    assert ("send", "a@example.com") in smtp.calls


def test_ssl_mode_uses_implicit_tls(fake, monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", "ssl")
    mailer.deliver("a@example.com", "Hi", "Body")
    smtp = fake.instances[0]
    assert smtp.context is not None
    assert not any(c[0] == "starttls" for c in smtp.calls)


def test_production_refuses_plain_smtp(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_security", "none")
    assert any("SMTP_SECURITY" in p for p in settings.production_problems())
