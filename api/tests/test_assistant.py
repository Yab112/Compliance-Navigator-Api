"""Interactive assistant: grounded dialogue flows, Amharic, the trained intent model, privacy."""

import pytest

from conftest import API
from services.db import execute, fetch_one

EM_DASH = "\u2014"


def _turn(client, conversation_id=None, message=None, action=None, headers=None):
    r = client.post(f"{API}/assistant/turn", json={"conversation_id": conversation_id, "message": message, "action": action},
                    headers=headers or {})
    assert r.status_code == 200, r.text
    payload = r.json()["payload"]
    reply = payload["reply"]
    # House style holds for every reply, including data we quote
    blob = reply["text"] + " ".join(str(c) for c in reply["cards"]) + str(reply.get("source") or "")
    assert EM_DASH not in blob
    return payload


def _model_or_skip():
    from assistant import nlu

    model = nlu.get_model()
    if model is None:
        pytest.skip("No assistant model trained (run scripts.train_assistant --activate)")
    return model


def test_greeting_gets_welcome_and_chips_not_a_path(client):
    _model_or_skip()
    p = _turn(client, message="hi")
    reply = p["reply"]
    assert reply["intent"] == "greeting"
    assert "What do you need" in reply["text"]
    assert len(reply["quick_replies"]) >= 4
    assert not any(c["kind"] == "path" for c in reply["cards"])
    assert "putting together" not in reply["text"]


def test_passport_disambiguation_then_sub_city_documents_and_path(client):
    _model_or_skip()
    p = _turn(client, message="i need a passport")
    widget = p["reply"]["widget"]
    assert widget and widget["key"] == "service"
    labels = [o["label"] for o in widget["options"]]
    assert "New passport" in labels and "Renewal" in labels
    cid = p["conversationId"]

    new = next(o for o in widget["options"] if o["label"] == "New passport")
    p = _turn(client, cid, action={"type": "choice", "key": "service", "value": new["value"]})
    assert p["reply"]["widget"]["kind"] == "sub_city"

    p = _turn(client, cid, action={"type": "choice", "key": "sub_city", "value": "bole"})
    widget = p["reply"]["widget"]
    assert widget["kind"] == "checklist" and widget["options"]

    p = _turn(client, cid, action={"type": "documents", "value": [widget["options"][0]["value"]]})
    path = next(c for c in p["reply"]["cards"] if c["kind"] == "path")
    assert path["steps"] and path["href"].startswith("/roadmap/")
    assert p["subCity"] == "bole"
    assert "Compliance Navigator path data" in p["reply"]["source"]


def test_renewal_resolves_directly_and_fee_answer_names_its_source(client):
    _model_or_skip()
    p = _turn(client, message="i want to renew my passport so what should i do")
    assert p["service"]["key"] == "mesob:mesob-728"
    assert p["reply"]["widget"]["kind"] == "sub_city"
    cid = p["conversationId"]
    p = _turn(client, cid, action={"type": "choice", "key": "sub_city", "value": "yeka"})
    p = _turn(client, cid, action={"type": "documents", "value": []})
    assert any(c["kind"] == "service" for c in p["reply"]["cards"])

    p = _turn(client, cid, message="how much does it cost?")
    assert p["reply"]["intent"] == "ask_fee"
    assert "21000" in p["reply"]["text"]
    assert "MESOB catalog" in p["reply"]["source"]


def test_amharic_greeting_and_passport_request(client):
    _model_or_skip()
    p = _turn(client, message="ሰላም")
    assert p["language"] == "am"
    assert p["reply"]["intent"] == "greeting"
    assert "ሰላም" in p["reply"]["text"]

    p = _turn(client, message="ፓስፖርት ማሳደስ እፈልጋለሁ")
    assert p["language"] == "am"
    assert p["service"]["key"] == "mesob:mesob-13"
    assert p["reply"]["widget"]["kind"] == "sub_city"
    assert "ክፍለ ከተማ" in p["reply"]["text"]


def test_out_of_scope_is_declined_politely(client):
    _model_or_skip()
    p = _turn(client, message="tell me a joke about football")
    assert p["reply"]["intent"] == "out_of_scope"
    assert "outside" in p["reply"]["text"]
    assert p["reply"]["quick_replies"]


def test_start_over_resets_the_conversation(client):
    _model_or_skip()
    p = _turn(client, message="i want to renew my passport")
    cid = p["conversationId"]
    p = _turn(client, cid, action={"type": "start_over"})
    assert p["service"] is None


def test_intent_model_classifies_fixed_samples():
    model = _model_or_skip()
    samples = {
        "hello there": "greeting", "thank you very much": "thanks", "ሰላም ጤና ይስጥልኝ": "greeting",
        "how much does a trade license cost": "ask_fee", "what documents should i bring": "ask_documents",
        "ስንት ብር ያስከፍላል": "ask_fee", "ምን ይዤ ልሂድ": "ask_documents", "i want to hire an agent": "hire_agent",
        "where is the office": "ask_location", "can someone apply for me": "ask_proxy",
        "what's the weather today": "out_of_scope", "bye": "goodbye", "start over": "start_over",
        "can i apply online": "ask_online", "how long does it take": "ask_time",
        "i need a birth certificate": "service_request",
    }
    correct = sum(model.predict(text).intent == want for text, want in samples.items())
    assert correct / len(samples) >= 0.75, f"{correct}/{len(samples)}"


def test_long_numbers_are_masked_before_storage(client):
    _model_or_skip()
    p = _turn(client, message="my fayda number is 1234 5678 9012, i need a passport")
    row = fetch_one(
        "select message_redacted from assistant_turns where conversation_id = %s order by id desc limit 1",
        (p["conversationId"],),
    )
    assert "1234" not in row["message_redacted"] and "######" in row["message_redacted"]


def test_admin_assistant_routes_need_admin(client, make_user):
    user, admin = make_user(), make_user("admin")
    assert client.get(f"{API}/admin/assistant/model", headers=user["headers"]).status_code == 403
    r = client.get(f"{API}/admin/assistant/model", headers=admin["headers"])
    assert r.status_code == 200 and "intents" in r.json()["payload"]

    # Label a message this test created, then remove the label so it never reaches training data
    p = _turn(client, message="zzqx unique test message")
    row = fetch_one("select id from assistant_turns where conversation_id = %s", (p["conversationId"],))
    try:
        r = client.post(f"{API}/admin/assistant/turns/{row['id']}/label", json={"intent": "greeting"}, headers=admin["headers"])
        assert r.status_code == 200
        bad = client.post(f"{API}/admin/assistant/turns/{row['id']}/label", json={"intent": "nope"}, headers=admin["headers"])
        assert bad.status_code == 422
    finally:
        execute("delete from assistant_turns where id = %s", (row["id"],))


def test_signed_in_conversation_is_private(client, make_user):
    _model_or_skip()
    owner, other = make_user(), make_user()
    p = _turn(client, message="hello", headers=owner["headers"])
    cid = p["conversationId"]
    assert client.get(f"{API}/assistant/conversations/{cid}", headers=owner["headers"]).status_code == 200
    assert client.get(f"{API}/assistant/conversations/{cid}", headers=other["headers"]).status_code == 404


def test_page_context_answers_without_restating_the_service(client):
    _model_or_skip()
    r = client.post(f"{API}/assistant/turn", json={"message": "how much does it cost?", "context_service": "path:trade_license"})
    assert r.status_code == 200
    payload = r.json()["payload"]
    assert payload["service"]["key"] == "path:trade_license"
    assert payload["reply"]["intent"] == "ask_fee"
    bad = client.post(f"{API}/assistant/turn", json={"message": "hi", "context_service": "drop table"})
    assert bad.status_code == 422


def test_cost_and_time_question_answers_both(client):
    from assistant.dialogue.answers import _answer
    from assistant.dialogue.data import _service_record

    rec = _service_record("mesob:mesob-728")
    question = "How much does it cost and how long does it take?"
    for intent in ("ask_fee", "ask_time"):
        text = _answer(intent, rec, {"lang": "en"}, question)["text"]
        assert "21000" in text and "Processing time" in text, text
    # A single question still gets a single answer
    assert "Processing time" not in _answer("ask_fee", rec, {"lang": "en"}, "how much does it cost?")["text"]
    assert "21000" not in _answer("ask_time", rec, {"lang": "en"}, "how much time does it take?")["text"]
