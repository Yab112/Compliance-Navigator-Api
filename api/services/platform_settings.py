"""
Business rules staff can change from the admin app: money and tax, the details printed on receipts,
and marketplace timings. Each field declares its type, limits and help text; the admin form is built
from that, and the server validates every change against it.

Secrets and infrastructure (payment keys, SMTP, database) stay in .env and are never editable here.
Values are cached for a few seconds, so a change reaches every request almost at once.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from config.config import settings
from services.db import execute, fetch_all, fetch_one


class SettingsError(Exception):
    pass


@dataclass(frozen=True)
class Field:
    key: str
    group: str
    label: str
    help: str
    type: str  # percent | money | int | bool | text
    default: Callable[[], Any]
    min: float | None = None
    max: float | None = None
    unit: str | None = None
    pattern: str | None = None
    pattern_hint: str | None = None
    required: bool = False
    placeholder: str | None = None
    applies: str | None = None  # when a change takes effect, shown next to the field
    choices: tuple[str, ...] = field(default_factory=tuple)


GROUPS = [
    {"key": "money", "title": "Money and tax", "am": "ገንዘብ እና ግብር",
     "description": "Commission, VAT and payouts. Amounts are frozen on each payment, so changes apply to new payments only."},
    {"key": "business", "title": "Business details on receipts", "am": "በደረሰኝ ላይ የሚታዩ መረጃዎች",
     "description": "Printed on every payment and payout receipt."},
    {"key": "marketplace", "title": "Marketplace rules", "am": "የገበያ ደንቦች",
     "description": "Timings and thresholds behind hires, Job Success and client records."},
    {"key": "vetting", "title": "Vetting Guday Geday and agencies", "am": "የአገልግሎት ሰጪዎች ማጣሪያ",
     "description": "What a provider must hand in to be approved and to stay listed. A change here is checked "
                    "against every provider at once."},
    {"key": "operations", "title": "Organizations and support", "am": "ድርጅቶች እና ድጋፍ",
     "description": "Upkeep of organization data and limits on the support desk."},
]

FIELDS: list[Field] = [
    Field("commission_percent", "money", "Platform commission", "Share of each job's price we keep.",
          "percent", lambda: settings.platform_commission_percent, 0, 50, "%", applies="New payments"),
    Field("vat_rate_percent", "money", "VAT rate", "Standard VAT rate (15% under Proclamation 1341/2024).",
          "percent", lambda: settings.vat_rate_percent, 0, 100, "%", applies="New payments"),
    Field("platform_vat_registered", "money", "We are VAT registered",
          "When on, VAT is charged on our commission and taken from the provider's share.",
          "bool", lambda: settings.platform_vat_registered, applies="New payments"),
    Field("min_payout_etb", "money", "Smallest withdrawal", "Providers can't ask for less than this.",
          "money", lambda: 100, 1, 1_000_000, "ETB", applies="New withdrawal requests"),
    Field("payout_approval_threshold_etb", "money", "Second approval for payouts from",
          "A payout of this amount or more needs a second staff member to approve it. 0 means every payout.",
          "money", lambda: 50_000, 0, 10_000_000, "ETB", applies="Payout approvals"),
    Field("payout_new_account_days", "money", "Flag recently changed bank accounts",
          "Payout review warns when the account was added or changed this recently.",
          "int", lambda: 7, 0, 90, "days", applies="Payout reviews"),

    Field("legal_name", "business", "Legal name", "Registered business name.", "text",
          lambda: settings.platform_legal_name, required=True, placeholder="Compliance Navigator PLC"),
    Field("tin", "business", "TIN", "Taxpayer identification number from the Ministry of Revenues.", "text",
          lambda: settings.platform_tin or "", pattern=r"^\d{10}$", pattern_hint="10 digits", placeholder="0001234567"),
    Field("vat_number", "business", "VAT registration number", "Leave empty if not VAT registered.", "text",
          lambda: settings.platform_vat_number or "", placeholder="VAT registration number"),
    Field("address", "business", "Address", "Shown under the legal name.", "text",
          lambda: settings.platform_address, required=True, placeholder="Bole, Addis Ababa"),

    Field("follow_up_hours", "marketplace", "Follow up unpaid deliveries after",
          "Delivered jobs not paid by then show in the support desk's follow-up list.",
          "int", lambda: 48, 1, 720, "hours"),
    Field("client_unpaid_days", "marketplace", "Count a delivery as unpaid after",
          "For the client record: a delivered job left unpaid this long counts against the hire rate.",
          "int", lambda: 7, 1, 90, "days"),
    Field("client_record_min", "marketplace", "Show a client's hire rate from",
          "Before this many decided requests a client shows as \"New client\".", "int", lambda: 3, 1, 50, "requests"),
    Field("job_success_min_jobs", "marketplace", "Show Job Success from",
          "Before this many closed jobs a provider shows as \"New\".", "int", lambda: 3, 1, 50, "closed jobs"),
    Field("license_validity_days", "marketplace", "Listing valid for", "How long an approval lasts before renewal.",
          "int", lambda: 365, 30, 1095, "days", applies="Approvals from now on"),
    Field("license_renew_window_days", "marketplace", "Allow renewal from",
          "How many days before a listing expires staff can renew it. Earlier renewals are refused.",
          "int", lambda: 60, 1, 365, "days before expiry"),
    Field("checkout_reuse_minutes", "marketplace", "Reuse an open checkout for",
          "A client pressing Pay again within this time gets the same checkout instead of a new one.",
          "int", lambda: 30, 5, 240, "minutes"),

    Field("vetting_min_education", "vetting", "Lowest education accepted",
          "Individual Guday Geday must show a certificate at this level or higher: grade_10, grade_12 "
          "(ESSLCE or grade 12 completion), tvet (TVET certificate or COC), diploma, or degree.",
          "text", lambda: "grade_12", required=True, pattern=r"^(grade_10|grade_12|tvet|diploma|degree)$",
          pattern_hint="one of grade_10, grade_12, tvet, diploma, degree", placeholder="grade_12",
          applies="Approvals and renewals from now on"),
    Field("police_clearance_max_age_days", "vetting", "Police clearance accepted for",
          "A clearance older than this, counted from its issue date, no longer counts. Listings whose "
          "clearance gets too old are suspended until a new one is verified.",
          "int", lambda: 180, 30, 730, "days after issue"),
    Field("police_clearance_remind_days", "vetting", "Remind providers before the clearance gets too old",
          "The provider gets a notification this many days before.", "int", lambda: 30, 1, 120, "days"),
    Field("vetting_references_required", "vetting", "References required",
          "When on, individuals need two references that staff have phoned and confirmed.",
          "bool", lambda: False, applies="Approvals and renewals from now on"),
    Field("vetting_guarantor_required", "vetting", "Guarantor (ተያዥ) required for individuals",
          "When on, Guday Geday and one-person agencies need a guarantor: details staff confirmed by phone, "
          "a signed guarantee letter and a copy of the guarantor's ID, both verified.",
          "bool", lambda: True, applies="At once: providers without one are hidden until it is verified"),
    Field("vetting_guarantor_required_company", "vetting", "Guarantor (ተያዥ) required for companies",
          "When on, agencies registered as companies need a verified guarantor too.",
          "bool", lambda: False, applies="At once: providers without one are hidden until it is verified"),

    Field("org_confirm_every_days", "operations", "Ask organizations to confirm services every",
          "Services not confirmed this long are flagged as due.", "int", lambda: 90, 7, 365, "days"),
    Field("support_tickets_per_ip_hour", "operations", "Support requests per visitor per hour",
          "Stops one address from flooding the support desk.", "int", lambda: 10, 1, 1000, "requests"),
    Field("feedback_flags_per_ip_hour", "operations", "'This is wrong' reports per visitor per hour",
          "Stops one address (or one account) from flooding the feedback queue and organizations' inboxes.",
          "int", lambda: 10, 1, 1000, "reports"),
]

BY_KEY = {f.key: f for f in FIELDS}
_TTL = 5.0
_cache: dict[str, Any] = {}
_loaded_at = 0.0


def _stored() -> dict[str, Any]:
    global _cache, _loaded_at
    if time.monotonic() - _loaded_at > _TTL:
        _cache = {r["key"]: r["value"] for r in fetch_all("select key, value from platform_settings")}
        _loaded_at = time.monotonic()
    return _cache


def clear_cache() -> None:
    global _loaded_at
    _loaded_at = 0.0


def get(key: str) -> Any:
    f = BY_KEY[key]
    stored = _stored()
    return stored[key] if key in stored else f.default()


def get_int(key: str) -> int:
    return int(get(key))


def _clean(f: Field, raw: Any) -> Any:
    """Validate one submitted value against its field; return it in its stored type."""
    if f.type == "bool":
        if not isinstance(raw, bool):
            raise SettingsError(f"{f.label}: choose on or off")
        return raw
    if f.type == "text":
        value = ("" if raw is None else str(raw)).strip()
        if f.required and not value:
            raise SettingsError(f"{f.label} is required")
        if len(value) > 200:
            raise SettingsError(f"{f.label} is too long")
        if value and f.pattern and not re.fullmatch(f.pattern, value):
            raise SettingsError(f"{f.label} must be {f.pattern_hint}")
        return value
    try:
        number = float(raw)
    except (TypeError, ValueError):
        raise SettingsError(f"{f.label} must be a number") from None
    if f.type == "int":
        if number != int(number):
            raise SettingsError(f"{f.label} must be a whole number")
        number = int(number)
    else:
        number = round(number, 2)
    if (f.min is not None and number < f.min) or (f.max is not None and number > f.max):
        raise SettingsError(f"{f.label} must be between {f.min:g} and {f.max:g}{' ' + f.unit if f.unit else ''}")
    return number


def admin_view() -> dict:
    """Groups of fields with their metadata, current value and who last changed them: the admin form's schema."""
    rows = {r["key"]: r for r in fetch_all("select key, value, updated_by, updated_at from platform_settings")}
    groups = []
    for g in GROUPS:
        fields = []
        for f in (f for f in FIELDS if f.group == g["key"]):
            row = rows.get(f.key)
            fields.append({
                "key": f.key, "label": f.label, "help": f.help, "type": f.type, "min": f.min, "max": f.max,
                "unit": f.unit, "pattern": f.pattern, "pattern_hint": f.pattern_hint, "required": f.required,
                "placeholder": f.placeholder, "applies": f.applies,
                "value": row["value"] if row else f.default(), "default": f.default(), "is_default": row is None,
                "updated_by": row and row["updated_by"], "updated_at": row and row["updated_at"],
            })
        groups.append({**g, "fields": fields})
    return {"groups": groups}


def update(values: dict[str, Any], actor: str) -> dict:
    """Save several fields at once; all are validated first, so a bad value changes nothing."""
    unknown = [k for k in values if k not in BY_KEY]
    if unknown:
        raise SettingsError(f"Unknown setting: {', '.join(unknown)}")
    cleaned = {k: _clean(BY_KEY[k], v) for k, v in values.items()}
    changed = []
    for key, value in cleaned.items():
        old = get(key)
        if old == value:
            continue
        execute(
            """
            insert into platform_settings (key, value, updated_by, updated_at) values (%s, %s, %s, now())
            on conflict (key) do update set value = excluded.value, updated_by = excluded.updated_by, updated_at = now()
            """,
            (key, json.dumps(value), actor),
        )
        execute("insert into platform_settings_history (key, old_value, new_value, changed_by) values (%s, %s, %s, %s)",
                (key, json.dumps(old), json.dumps(value), actor))
        changed.append(key)
    clear_cache()
    _requirements_changed(changed)
    return {**admin_view(), "changed": changed}


def _requirements_changed(keys) -> None:
    """A vetting setting decides who may work: check every provider again (services/provider_service.py)."""
    if not any(BY_KEY[k].group == "vetting" for k in keys):
        return
    from services import provider_service

    provider_service.refresh_readiness_all()


def reset(key: str, actor: str) -> dict:
    """Go back to the default (.env or built-in) value."""
    if key not in BY_KEY:
        raise SettingsError(f"Unknown setting: {key}")
    old = get(key)
    if execute("delete from platform_settings where key = %s", (key,)):
        execute("insert into platform_settings_history (key, old_value, new_value, changed_by) values (%s, %s, %s, %s)",
                (key, json.dumps(old), json.dumps(BY_KEY[key].default()), f"{actor} (reset to default)"))
    clear_cache()
    _requirements_changed([key])
    return admin_view()


def history(limit: int = 25, offset: int = 0) -> dict:
    rows = fetch_all(
        "select id, key, old_value, new_value, changed_by, changed_at from platform_settings_history "
        "order by changed_at desc, id desc limit %s offset %s",
        (limit, offset),
    )
    for r in rows:
        f = BY_KEY.get(r["key"])
        r["label"] = f.label if f else r["key"]
        r["unit"] = f.unit if f else None
    total = fetch_one("select count(*) as n from platform_settings_history")["n"]
    return {"items": rows, "total": total}
