"""Sandbox Fayda verification for tests (FAYDA_MODE=sandbox, the default)."""

import random
from urllib.parse import parse_qs, urlparse

from conftest import API


def random_fin() -> str:
    return "".join(random.choice("0123456789") for _ in range(12))


def start_state(client, user) -> str:
    r = client.post(f"{API}/guday/fayda/start", headers=user["headers"])
    assert r.status_code == 200, r.text
    return parse_qs(urlparse(r.json()["payload"]["redirect_url"]).query)["state"][0]


def sandbox_verify(client, user, *, fin: str | None = None, name: str = "Test Agent", otp: str = "111111"):
    state = start_state(client, user)
    return client.post(
        f"{API}/guday/fayda/sandbox/complete",
        json={"state": state, "id_number": fin or random_fin(), "full_name": name, "otp": otp},
        headers=user["headers"],
    )


def ensure_verified(client, user) -> None:
    status = client.get(f"{API}/guday/fayda/status", headers=user["headers"]).json()["payload"]
    if not status["verification"]:
        r = sandbox_verify(client, user)
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------- live mode (local keys, no network)

LIVE_ISSUER = "https://esignet.test.invalid"
LIVE_CLIENT_ID = "test-client-id"


def rsa_key():
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_for(key, kid: str = "fayda-1") -> dict:
    import json as _json

    from jwt.algorithms import RSAAlgorithm

    jwk = _json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    return {"keys": [{**jwk, "kid": kid, "use": "sig", "alg": "RS256"}]}


def sign(claims: dict, key, kid: str = "fayda-1") -> str:
    import jwt

    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def id_token_claims(nonce: str, **overrides) -> dict:
    import time

    now = int(time.time())
    return {"iss": LIVE_ISSUER, "aud": LIVE_CLIENT_ID, "sub": "fayda-sub-1", "nonce": nonce,
            "iat": now, "exp": now + 300, **overrides}


def use_live_fayda(monkeypatch, fayda_key) -> None:
    """Live mode with our own key pair standing in for Fayda's: the JWKS fetch returns its public key."""
    import jwt
    from cryptography.hazmat.primitives import serialization

    from config.config import settings

    client_pem = rsa_key().private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()).decode()
    for name, value in {
        "fayda_mode": "live", "fayda_client_id": LIVE_CLIENT_ID, "fayda_issuer": LIVE_ISSUER,
        "fayda_authorize_url": f"{LIVE_ISSUER}/authorize", "fayda_token_url": f"{LIVE_ISSUER}/token",
        "fayda_userinfo_url": f"{LIVE_ISSUER}/userinfo", "fayda_jwks_url": f"{LIVE_ISSUER}/jwks",
        "fayda_private_key": client_pem,
    }.items():
        monkeypatch.setattr(settings, name, value)
    jwks = jwks_for(fayda_key)
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: jwks)


def fake_fayda_http(monkeypatch, *, id_token: str, userinfo: str) -> None:
    """Token and userinfo endpoints answer with the given ID token and userinfo body (JWT or JSON text)."""
    import json as _json

    from services import id_verification

    class Response:
        def __init__(self, text: str):
            self.status_code, self.text = 200, text

        def json(self):
            return _json.loads(self.text)

    class Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, data=None, **kw):
            return Response(_json.dumps({"id_token": id_token, "access_token": "at"}))

        def get(self, url, **kw):
            return Response(userinfo)

    monkeypatch.setattr(id_verification.httpx, "Client", Client)
