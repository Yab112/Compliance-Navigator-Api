"""National ID verification with Fayda (Ethiopia's National ID Program, MOSIP eSignet).

live:    OIDC authorization-code flow: PKCE (S256), private_key_jwt client
         authentication, signed userinfo (JWS) checked against the eSignet JWKS.
sandbox: same start/state handling, but the "Fayda" screen is our own test page
         and the one-time code is always 111111. Never use sandbox in production.

The full Fayda number never leaves this module: only a keyed hash (to stop one
ID verifying two accounts) and the last four digits are stored.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt
from psycopg.errors import UniqueViolation

from config.config import settings
from services.db import connection, fetch_one

log = logging.getLogger(__name__)

STATE_TTL = timedelta(minutes=10)
SANDBOX_OTP = "111111"
# Wrong one-time codes allowed on one verification before it is burned and the person starts again
OTP_ATTEMPTS = 3
ACR_VALUES = "mosip:idp:acr:generated-code mosip:idp:acr:biometrics mosip:idp:acr:linked-wallet"
USERINFO_CLAIMS = ("name", "birthdate", "gender", "phone_number", "picture", "address", "individual_id")

PUBLIC_COLUMNS = """
  id::text, mode, status, method, id_type, id_last4, verified_name, birthdate, gender,
  verified_at, created_at
"""


class VerificationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def mode() -> str:
    m = (settings.fayda_mode or "off").lower()
    if m == "sandbox" and settings.is_production:
        # config.py already refuses to start like this; never accept made-up IDs in production regardless
        return "off"
    return m if m in ("off", "sandbox", "live") else "off"


def is_test(method: str | None) -> bool:
    """A sandbox verification proves nothing: show it as a test ID, never as verified."""
    return method == "fayda_sandbox"


def retire_sandbox_verifications() -> int:
    """In live mode, test (sandbox) verifications left over from before stop counting anywhere: the person's
    record is superseded and their provider profile loses the ID badge until they verify with real Fayda.
    Runs at startup; does nothing outside live mode. Returns how many were retired."""
    if mode() != "live":
        return 0
    with connection() as conn, conn.transaction():
        rows = conn.execute(
            """
            update id_verifications set status = 'superseded', error = 'sandbox_retired'
            where method = 'fayda_sandbox' and status = 'verified'
            returning id
            """
        ).fetchall()
        conn.execute(
            """
            update providers set national_id_verified = false, updated_at = now()
            where id_verification_method = 'fayda_sandbox' and national_id_verified
            """
        )
    if rows:
        log.warning("Retired %s test (sandbox) ID verifications now that Fayda is live", len(rows))
    return len(rows)


def is_required() -> bool:
    return mode() != "off"


# ---------------------------------------------------------------- helpers


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _hash_id(number: str) -> str:
    pepper = (settings.id_hash_pepper or settings.secret_key).encode()
    return hmac.new(pepper, number.encode(), hashlib.sha256).hexdigest()


def masked(id_type: str | None, last4: str | None) -> str:
    return f"{id_type or 'ID'} •••• {last4 or '????'}"


def _private_key() -> str:
    raw = settings.fayda_private_key or ""
    if raw and "BEGIN" not in raw and Path(raw).exists():
        return Path(raw).read_text()
    return raw.replace("\\n", "\n")


def _live_config_missing() -> list[str]:
    needed = {
        "FAYDA_CLIENT_ID": settings.fayda_client_id,
        "FAYDA_AUTHORIZE_URL": settings.fayda_authorize_url,
        "FAYDA_TOKEN_URL": settings.fayda_token_url,
        "FAYDA_USERINFO_URL": settings.fayda_userinfo_url,
        "FAYDA_JWKS_URL": settings.fayda_jwks_url,
        "FAYDA_PRIVATE_KEY": settings.fayda_private_key,
    }
    return [k for k, v in needed.items() if not v]


# ---------------------------------------------------------------- reads


def current(user_id: str) -> dict | None:
    """The user's active (verified) identity, if any."""
    row = fetch_one(
        f"select {PUBLIC_COLUMNS} from id_verifications where user_id = %s and status = 'verified'",
        (user_id,),
    )
    if row:
        row["masked_id"] = masked(row["id_type"], row["id_last4"])
    return row


def status(user_id: str) -> dict:
    return {"mode": mode(), "required": is_required(), "verification": current(user_id)}


# ---------------------------------------------------------------- start


def start(user_id: str) -> dict:
    m = mode()
    if m == "off":
        raise VerificationError("National ID verification is turned off", 404)
    if m == "live" and (missing := _live_config_missing()):
        raise VerificationError(f"Fayda is not configured: {', '.join(missing)}", 503)

    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    with connection() as conn:
        conn.execute(
            """
            insert into id_verifications (user_id, mode, state, nonce, code_verifier, expires_at)
            values (%s, %s, %s, %s, %s, now() + %s)
            """,
            (user_id, m, state, nonce, verifier, STATE_TTL),
        )

    if m == "sandbox":
        return {"mode": m, "redirect_url": f"{settings.fayda_sandbox_url}?{urlencode({'state': state})}"}

    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    claims = {"userinfo": {c: {"essential": c in ("name", "individual_id")} for c in USERINFO_CLAIMS}, "id_token": {}}
    params = {
        "client_id": settings.fayda_client_id,
        "redirect_uri": settings.fayda_redirect_uri,
        "response_type": "code",
        "scope": "openid profile",
        "state": state,
        "nonce": nonce,
        "acr_values": ACR_VALUES,
        "claims": json.dumps(claims, separators=(",", ":")),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "claims_locales": "en am",
        "ui_locales": "en",
        "display": "page",
        "prompt": "consent",
    }
    return {"mode": m, "redirect_url": f"{settings.fayda_authorize_url}?{urlencode(params)}"}


def _take_pending(conn, user_id: str, state: str, expected_mode: str) -> dict:
    row = conn.execute(
        "select * from id_verifications where state = %s for update", (state,)
    ).fetchone()
    if not row or str(row["user_id"]) != user_id or row["mode"] != expected_mode:
        raise VerificationError("This verification link is not valid", 400)
    if row["status"] != "pending":
        raise VerificationError("This verification has ended. Go back and start the ID check again", 409)
    if row["expires_at"] < datetime.now(timezone.utc):
        conn.execute("update id_verifications set status = 'failed', error = 'expired' where id = %s", (row["id"],))
        raise VerificationError("The verification expired. Start again", 410)
    return row


def _finish(conn, row: dict, *, method: str, id_type: str, number: str, name: str | None,
            birthdate: str | None = None, gender: str | None = None, phone: str | None = None) -> None:
    id_hash = _hash_id(number)
    other = conn.execute(
        "select user_id from id_verifications where id_hash = %s and status = 'verified' and user_id <> %s",
        (id_hash, row["user_id"]),
    ).fetchone()
    if other:
        conn.execute("update id_verifications set status = 'failed', error = 'duplicate' where id = %s", (row["id"],))
        raise VerificationError("This national ID is already verified on another account", 409)
    conn.execute(
        "update id_verifications set status = 'superseded' where user_id = %s and status = 'verified'",
        (row["user_id"],),
    )
    conn.execute(
        """
        update id_verifications set status = 'verified', method = %s, id_type = %s, id_hash = %s,
          id_last4 = %s, verified_name = %s, birthdate = %s, gender = %s, phone = %s, verified_at = now()
        where id = %s
        """,
        (method, id_type, id_hash, number[-4:], name, birthdate, gender, phone, row["id"]),
    )


def _run(fn):
    """Errors inside the transaction must still persist the 'failed' marker."""
    try:
        with connection() as conn:
            with conn.transaction():
                return fn(conn)
    except UniqueViolation as exc:
        raise VerificationError("This national ID is already verified on another account", 409) from exc


# ---------------------------------------------------------------- sandbox


def complete_sandbox(user_id: str, *, state: str, id_number: str, full_name: str, otp: str,
                     birthdate: str | None = None, gender: str | None = None) -> dict:
    if mode() != "sandbox":
        raise VerificationError("Not found", 404)
    digits = re.sub(r"\D", "", id_number)
    if len(digits) not in (12, 16):
        raise VerificationError("Enter a 12-digit FIN or a 16-digit FCN")

    failure: list[VerificationError] = []

    def work(conn):
        row = _take_pending(conn, user_id, state, "sandbox")
        if otp != SANDBOX_OTP:
            # While pending, error counts wrong codes ("otp:2"); the last allowed miss burns the state
            tries = int(m.group(1)) + 1 if (m := re.fullmatch(r"otp:(\d+)", row["error"] or "")) else 1
            if tries >= OTP_ATTEMPTS:
                conn.execute("update id_verifications set status = 'failed', error = 'otp' where id = %s", (row["id"],))
                failure.append(VerificationError(
                    f"Wrong one-time code {OTP_ATTEMPTS} times. Go back and start the ID check again", 409))
            else:
                conn.execute("update id_verifications set error = %s where id = %s", (f"otp:{tries}", row["id"]))
                left = OTP_ATTEMPTS - tries
                failure.append(VerificationError(
                    f"Wrong one-time code (test mode code is 111111). {left} {'try' if left == 1 else 'tries'} left"))
            return
        _finish(conn, row, method="fayda_sandbox", id_type="FIN" if len(digits) == 12 else "FCN",
                number=digits, name=full_name.strip(), birthdate=birthdate, gender=gender)

    try:
        _run(work)
    except VerificationError as exc:
        if exc.status_code in (409, 410):
            _persist_failure(state, str(exc))
        raise
    if failure:
        raise failure[0]
    return current(user_id)


def _persist_failure(state: str, error: str) -> None:
    # The rolled-back transaction lost its status update; record the outcome
    with connection() as conn:
        conn.execute(
            "update id_verifications set status = 'failed', error = %s where state = %s and status = 'pending'",
            (error[:200], state),
        )


# ---------------------------------------------------------------- live (eSignet)


def _client_assertion() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": settings.fayda_client_id,
            "sub": settings.fayda_client_id,
            "aud": settings.fayda_token_url,
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
        },
        _private_key(),
        algorithm="RS256",
    )


def _verify_jws(token: str, *, audience: str | None = None) -> dict:
    key = jwt.PyJWKClient(settings.fayda_jwks_url).get_signing_key_from_jwt(token)
    issuer = settings.fayda_issuer or None
    return jwt.decode(
        token, key.key, algorithms=["RS256", "PS256", "ES256"],
        audience=audience, issuer=issuer,
        options={"verify_aud": audience is not None, "verify_iss": issuer is not None},
    )


def _exchange(row: dict, code: str) -> dict:
    with httpx.Client(timeout=20) as http:
        tok = http.post(
            settings.fayda_token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.fayda_redirect_uri,
                "client_id": settings.fayda_client_id,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": _client_assertion(),
                "code_verifier": row["code_verifier"],
            },
        )
        if tok.status_code != 200:
            raise VerificationError("Fayda rejected the sign-in, please try again", 502)
        tokens = tok.json()
        id_claims = _verify_jws(tokens["id_token"], audience=settings.fayda_client_id)
        if id_claims.get("nonce") != row["nonce"]:
            raise VerificationError("Fayda response did not match this request", 400)
        info = http.get(settings.fayda_userinfo_url, headers={"Authorization": f"Bearer {tokens['access_token']}"})
        if info.status_code != 200:
            raise VerificationError("Could not read your Fayda details", 502)
    # eSignet returns userinfo as a signed JWT
    body = info.text.strip()
    claims = _verify_jws(body) if body.count(".") == 2 else info.json()
    # The details must belong to the person who signed in
    if claims.get("sub") and id_claims.get("sub") and claims["sub"] != id_claims["sub"]:
        raise VerificationError("Fayda response did not match this request", 400)
    return claims


def complete_live(user_id: str, *, code: str, state: str) -> dict:
    if mode() != "live":
        raise VerificationError("Fayda live verification is not enabled", 404)

    def work(conn):
        row = _take_pending(conn, user_id, state, "live")
        claims = _exchange(row, code)
        number = re.sub(r"\D", "", str(claims.get("individual_id") or ""))
        id_type = "FIN" if len(number) == 12 else "FCN" if len(number) == 16 else "SUB"
        if id_type == "SUB":
            number = str(claims.get("sub") or "")
        if not number:
            raise VerificationError("Fayda did not return an identity", 502)
        _finish(conn, row, method="fayda", id_type=id_type, number=number, name=claims.get("name"),
                birthdate=claims.get("birthdate"), gender=claims.get("gender"), phone=claims.get("phone_number"))

    try:
        _run(work)
    except VerificationError as exc:
        _persist_failure(state, str(exc))
        raise
    except (httpx.HTTPError, jwt.PyJWTError) as exc:
        _persist_failure(state, f"{type(exc).__name__}")
        raise VerificationError("Could not complete Fayda verification, please try again", 502) from exc
    return current(user_id)
