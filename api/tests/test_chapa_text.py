"""Chapa refuses customization text with punctuation or non-English letters; job titles must never block a payment."""

import re

from services.payment_service.gateways import ChapaGateway


def test_job_titles_become_text_chapa_accepts():
    allowed = re.compile(r"^[A-Za-z0-9 ._-]+$")
    for title in ("Renew my passport: urgent!", "ፓስፖርት ማደስ", "Trade licence (new) – Bole, A/A", "", "  "):
        out = ChapaGateway._plain(title, 50, "Payment for a job")
        assert allowed.match(out) and len(out) <= 50
    assert ChapaGateway._plain("ፓስፖርት", 50, "Payment for a job") == "Payment for a job"
    assert ChapaGateway._plain("Renew: my passport", 16, "x") == "Renew my passpor"
