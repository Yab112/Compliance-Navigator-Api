"""Whole conversations, turn by turn: the assistant must keep track of what it already showed.

Each test replays a real exchange that went wrong once, so it can't silently come back.
"""

import pytest

from conftest import API


def _turn(client, cid=None, message=None, action=None):
    r = client.post(f"{API}/assistant/turn", json={"conversation_id": cid, "message": message, "action": action})
    assert r.status_code == 200, r.text
    return r.json()["payload"]


def _providers_shown(client, message="i want to hire a guday geday agent", language=None, at_least=2):
    p = _turn(client, message="hi")
    cid = p["conversationId"]
    if language:
        _turn(client, cid, action={"type": "language", "value": language})
    p = _turn(client, cid, message=message)
    cards = [c for c in p["reply"]["cards"] if c["kind"] == "providers"]
    if not cards or len(cards[0]["items"]) < at_least:
        pytest.skip("Needs approved providers (run scripts.seed_providers)")
    return cid, p, cards[0]["items"]


def _kinds(payload):
    return [c["kind"] for c in payload["reply"]["cards"]]


def test_follow_ups_about_a_listed_provider(client):
    """Amharic button pressed, English typed, then questions about one provider."""
    cid, p, items = _providers_shown(client, language="am")
    assert p["language"] == "en"  # typed English wins over the button
    who = items[0]
    first = who["name"].split()[0]

    p = _turn(client, cid, message=f"okay what {first.lower()} did")
    assert p["reply"]["intent"] == "provider_info"
    assert p["reply"]["cards"][0]["items"][0]["slug"] == who["slug"]
    assert who["name"] in p["reply"]["text"]

    p = _turn(client, cid, message="sure can i see her last closed jobs")
    assert p["reply"]["intent"] == "provider_info" and p["reply"]["cards"][0]["items"][0]["slug"] == who["slug"]
    assert "checklist" in _kinds(p) or "no completed jobs" in p["reply"]["text"]

    p = _turn(client, cid, message="how much does she charge")
    assert p["reply"]["intent"] == "provider_info" and first in p["reply"]["text"]

    p = _turn(client, cid, message="can i call him directly")
    assert "accepts your request" in p["reply"]["text"]


def test_ordinals_and_switching_provider(client):
    cid, _, items = _providers_shown(client)
    p = _turn(client, cid, message="show me reviews of the second one")
    assert p["reply"]["cards"][0]["items"][0]["slug"] == items[1]["slug"]
    p = _turn(client, cid, message="and their fees")  # stays on the second one
    assert p["reply"]["cards"][0]["items"][0]["slug"] == items[1]["slug"]
    first = items[0]["name"].split()[0]
    p = _turn(client, cid, message=f"what about {first}")
    assert p["reply"]["cards"][0]["items"][0]["slug"] == items[0]["slug"]


def test_pronouns_dont_hijack_other_topics(client):
    cid, _, _ = _providers_shown(client)
    p = _turn(client, cid, message="i want to renew my passport")
    assert p["reply"]["intent"] != "provider_info"
    # "they" now means the passport office, not a provider
    p = _turn(client, cid, message="what do they ask for")
    assert p["reply"]["intent"] != "provider_info"


def test_service_words_in_company_names_are_not_names(client):
    cid, _, _ = _providers_shown(client, message="find me a customs clearing agent", at_least=1)
    p = _turn(client, cid, message="i need customs clearing for my shipment")
    assert p["reply"]["intent"] != "provider_info"


def test_amharic_follow_up(client):
    cid, _, items = _providers_shown(client)
    first = items[0]["name"].split()[0]
    p = _turn(client, cid, message=f"{first} የሰራቸው ስራዎች")
    assert p["language"] == "am" and p["reply"]["cards"][0]["items"][0]["slug"] == items[0]["slug"]


def test_handoff_survives_picking_a_service(client):
    p = _turn(client, message="my fayda verification is not working, can someone from your team call me back")
    cid = p["conversationId"]
    _turn(client, cid, action={"type": "form", "key": "contact", "value": {"name": "Test Person", "phone": "0911000111"}})
    p = _turn(client, cid, action={"type": "confirm", "value": "handoff"})
    assert p["channel"] == "human"
    _turn(client, cid, action={"type": "channel", "value": "agent"})
    p = _turn(client, cid, message="i want to renew my passport")
    assert p["ticket"] is not None  # the open request is still linked to this chat


def test_brokers_are_out_of_scope_but_office_work_is_not(client):
    p = _turn(client, message="i am thinking to hire new broker")
    cid = p["conversationId"]
    assert "don't list" in p["reply"]["text"] and not [c for c in p["reply"]["cards"] if c["kind"] == "providers"]
    p = _turn(client, cid, message="i need a house for rent in bole")
    assert "don't list" in p["reply"]["text"]
    p = _turn(client, cid, message="ደላላ እፈልጋለሁ")
    assert p["language"] == "am" and "ደላሎችን አንዘረዝርም" in p["reply"]["text"]
    # The office side of property is still ours
    p = _turn(client, cid, message="how do i transfer car ownership")
    assert "don't list" not in p["reply"]["text"]
    p = _turn(client, cid, message="find me someone for customs clearing")
    if not p["reply"]["cards"]:
        pytest.skip("Needs a listed agency (run scripts.seed_providers --make-ready)")
    assert {i["type"] for i in p["reply"]["cards"][0]["items"]} == {"agency"}
