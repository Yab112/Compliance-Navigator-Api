"""Staff change business rules from the admin app; every change is validated, applied at once and kept on record."""

import json

import pytest

from conftest import API
from services import platform_settings
from services.db import execute, fetch_all
from test_providers import _approved, _deliver, _hire, _job, _pay


@pytest.fixture(autouse=True)
def _defaults():
    """Tests share the app's database: start from defaults, then put back whatever staff had saved."""
    saved = fetch_all("select key, value, updated_by, updated_at from platform_settings")
    execute("delete from platform_settings")
    platform_settings.clear_cache()
    yield
    execute("delete from platform_settings")
    for row in saved:
        execute("insert into platform_settings (key, value, updated_by, updated_at) values (%s, %s, %s, %s)",
                (row["key"], json.dumps(row["value"]), row["updated_by"], row["updated_at"]))
    platform_settings.clear_cache()


def _fields(payload):
    return {f["key"]: f for g in payload["groups"] for f in g["fields"]}


def test_only_staff_see_and_change_settings(client, make_user):
    user = make_user()
    assert client.get(f"{API}/admin/settings", headers=user["headers"]).status_code == 403
    assert client.patch(f"{API}/admin/settings", json={"values": {"commission_percent": 1}},
                        headers=user["headers"]).status_code == 403


def test_form_schema_lists_groups_types_limits_and_defaults(client, make_user):
    admin = make_user("admin")
    fields = _fields(client.get(f"{API}/admin/settings", headers=admin["headers"]).json()["payload"])
    c = fields["commission_percent"]
    assert c["type"] == "percent" and c["min"] == 0 and c["max"] == 50 and c["is_default"] and c["value"] == c["default"]
    assert fields["platform_vat_registered"]["type"] == "bool" and fields["tin"]["pattern_hint"] == "10 digits"


def test_bad_values_change_nothing(client, make_user):
    admin = make_user("admin")
    patch = lambda values: client.patch(f"{API}/admin/settings", json={"values": values},  # noqa: E731
                                        headers=admin["headers"])
    r = patch({"commission_percent": 12, "vat_rate_percent": 200})
    assert r.status_code == 400 and "VAT rate" in r.json()["detail"]
    assert platform_settings.get("commission_percent") != 12  # all or nothing
    assert patch({"tin": "12ab"}).status_code == 400
    assert patch({"follow_up_hours": 2.5}).status_code == 400
    assert patch({"legal_name": "  "}).status_code == 400
    assert patch({"platform_vat_registered": "yes"}).status_code == 400
    assert patch({"no_such_setting": 1}).status_code == 400


def test_commission_change_applies_to_new_payments_and_is_logged(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    r = client.patch(f"{API}/admin/settings", json={"values": {"commission_percent": 12, "min_payout_etb": 300}},
                     headers=admin["headers"])
    assert r.status_code == 200 and set(r.json()["payload"]["changed"]) == {"commission_percent", "min_payout_etb"}
    assert client.get(f"{API}/payments/config").json()["payload"]["commission_percent"] == 12

    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=1000)
    _deliver(client, agent, hire["id"])
    _pay(client, customer, hire["id"])
    earnings = client.get(f"{API}/providers/me/earnings", headers=agent["headers"]).json()["payload"]
    assert earnings["balance"] == 1000 - 120 - 18  # 12% commission and 15% VAT on it
    assert earnings["min_payout"] == 300
    client.put(f"{API}/providers/me/payout", json={"bank_code": "sim-cbe", "account_number": "1000 2345 6789",
                                                   "account_name": "Test Agent"}, headers=agent["headers"])
    assert client.post(f"{API}/providers/me/payouts", json={"amount": 200}, headers=agent["headers"]).status_code == 400

    history = client.get(f"{API}/admin/settings/history", headers=admin["headers"]).json()["payload"]
    latest = {h["key"]: h for h in history["items"][:2]}
    assert latest["commission_percent"]["new_value"] == 12 and latest["commission_percent"]["changed_by"] == admin["email"]

    reset = client.delete(f"{API}/admin/settings/commission_percent", headers=admin["headers"])
    assert reset.status_code == 200 and _fields(reset.json()["payload"])["commission_percent"]["is_default"]
    assert client.delete(f"{API}/admin/settings/nope", headers=admin["headers"]).status_code == 404
    execute("delete from platform_settings_history where changed_by = %s or changed_by like %s",
            (admin["email"], admin["email"] + "%"))
