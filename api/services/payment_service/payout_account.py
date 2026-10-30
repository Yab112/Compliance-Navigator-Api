"""The provider's payout bank account."""

from __future__ import annotations

import logging
import re
import threading
import time

from services import notifications, payment_service, platform_settings
from services.db import execute, fetch_one

from .gateways import PaymentError, mode

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- provider payout account


BANKS_TTL = 12 * 3600  # seconds; banks rarely change
_banks_cache: dict[str, tuple[float, list[dict]]] = {}  # gateway name -> (fetched at, list)
_banks_lock = threading.Lock()


def banks(*, refresh: bool = False) -> list[dict]:
    """The gateway's bank list, kept for a while. If the gateway fails, the last good list is served."""
    gw = payment_service.gateway()
    cached = _banks_cache.get(gw.name)
    if cached and not refresh and time.monotonic() - cached[0] < BANKS_TTL:
        return cached[1]
    # Someone is already refreshing an old list: serve that one instead of waiting on the gateway too
    if cached and not _banks_lock.acquire(blocking=False):
        return cached[1]
    if not cached:
        _banks_lock.acquire()
    try:
        cached = _banks_cache.get(gw.name)
        if cached and not refresh and time.monotonic() - cached[0] < BANKS_TTL:
            return cached[1]  # another request refreshed it while this one waited
        try:
            items = gw.banks()
        except PaymentError:
            if cached:
                log.warning("Bank list unavailable from %s; serving the last good list", gw.name)
                return cached[1]
            raise
        if items:
            _banks_cache[gw.name] = (time.monotonic(), items)
        return items
    finally:
        _banks_lock.release()


def _waiting_payouts(provider_id: str) -> int:
    return fetch_one("select count(*) as c from payouts where provider_id = %s and status in ('requested', 'approved')",
                     (provider_id,))["c"]


def payout_view(provider: dict) -> dict:
    verified = provider.get("verified_name")
    account_name = provider.get("payout_account_name")
    return {
        "ready": bool(provider.get("payout_ready")),
        "bank_name": provider.get("payout_bank_name"),
        "account_name": account_name,
        "account_last4": provider.get("payout_account_last4"),
        "set_at": provider.get("payout_set_at"),
        "commission_percent": platform_settings.get("commission_percent"),
        "mode": mode(),
        # The holder name must match the name on the provider's verified ID (or their company's name)
        "verified_name": verified,
        "name_matches": None if not account_name else names_match(
            account_name, verified, provider.get("legal_name"), None if verified else provider.get("display_name")),
        # The account can't change while a payout is on its way to it
        "locked": bool(provider.get("id")) and _waiting_payouts(provider["id"]) > 0,
    }


def set_payout(user_id: str, *, bank_code: str, account_number: str, account_name: str) -> dict:
    """Where the provider's withdrawals are sent. Only the last 4 digits are ever shown again."""
    from core.crypto import encrypt
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    if provider["status"] != "approved":
        raise PaymentError("Your profile must be approved before you can receive payouts", 403)
    account_number = re.sub(r"\s", "", account_number)
    if not re.fullmatch(r"\d{6,20}", account_number):
        raise PaymentError("Enter the account number using digits only")
    account_name = re.sub(r"\s+", " ", account_name).strip()
    if len(account_name) < 2:
        raise PaymentError("Enter the account holder's name exactly as the bank has it")
    # The cached list is enough; only a code it doesn't know asks the gateway again
    bank = next((b for b in banks() if b["code"] == str(bank_code)), None)
    if not bank:
        bank = next((b for b in banks(refresh=True) if b["code"] == str(bank_code)), None)
    if not bank:
        raise PaymentError("Choose your bank from the list")
    # Money already asked for goes to the account it was asked for; changing it now would confuse that
    if _waiting_payouts(provider["id"]):
        raise PaymentError("You have a payout on its way. You can change your bank account once it is paid or refused.", 409)
    execute(
        """
        update providers set payout_account_enc = %s, payout_bank_code = %s, payout_bank_name = %s,
          payout_account_name = %s, payout_account_last4 = %s, payout_set_at = now(), updated_at = now()
        where id = %s
        """,
        (encrypt(account_number), str(bank_code), bank["name"], account_name, account_number[-4:], provider["id"]),
    )
    log.info("Payout account changed for provider %s (%s ••••%s)", provider["id"], bank["name"], account_number[-4:])
    # A security notice: if someone else changed it, the owner finds out at once
    title = "Your payout bank account was changed" if provider.get("payout_account_last4") else "Payout bank account added"
    notifications.notify([user_id], kind="payout", title=title,
                         body=f"{bank['name']} ••••{account_number[-4:]} in the name of {account_name}. "
                              "If this wasn't you, change your password and contact support.",
                         link="/me/provider?tab=earnings")
    return payout_view(provider_service.get_for_user(user_id))


def _name_tokens(name: str | None) -> set[str]:
    return {w for w in re.findall(r"[^\W\d_]+", (name or "").lower()) if len(w) > 1}


def names_match(holder: str | None, *candidates: str | None) -> bool:
    """The bank account holder is the provider: same name, or one name contains the other ("Meron Tadesse Alemu")."""
    h = _name_tokens(holder)
    for c in candidates:
        t = _name_tokens(c)
        if h and t and (h <= t or t <= h or len(h & t) >= 2):
            return True
    return False
