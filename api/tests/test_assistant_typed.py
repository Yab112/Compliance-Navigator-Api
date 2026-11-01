"""The assistant as people on phones use it: typed answers instead of taps, honest "not in my guide"
instead of a wrong guess, and the start-up questions (business form, tax rules) answered directly."""

from assistant.dialogue import typed
from test_assistant import _turn


def _cid(p):
    return p["conversationId"]


def test_typed_answers_walk_the_passport_flow_without_a_single_tap(client):
    p = _turn(client, message="I need a passport")
    assert [o["label"] for o in p["reply"]["widget"]["options"]][0] == "New passport"
    p = _turn(client, conversation_id=_cid(p), message="new")
    assert p["reply"]["intent"] == "typed_choice"
    assert p["service"]["key"] == "path:passport"
    assert p["reply"]["widget"]["kind"] == "sub_city"
    p = _turn(client, conversation_id=_cid(p), message="Bole")
    assert p["subCity"] == "bole"
    p = _turn(client, conversation_id=_cid(p), message="none")
    assert any(c["kind"] == "path" for c in p["reply"]["cards"])
    assert "remaining days" not in p["reply"]["text"]


def test_pick_by_number_word_start_and_yes():
    offered = {"widget": "choice", "chips": [], "options": [
        {"label": "New passport", "action": {"type": "choice", "key": "service", "value": "a"}},
        {"label": "Renewal", "action": {"type": "choice", "key": "service", "value": "b"}},
        {"label": "Lost or stolen", "action": {"type": "choice", "key": "service", "value": "c"}},
    ]}
    assert typed.pick("2", offered)["value"] == "b"
    assert typed.pick("the last one", offered)["value"] == "c"
    assert typed.pick("renew", offered)["value"] == "b"
    assert typed.pick("new", offered)["value"] == "a"  # not "renewal", which only contains "new"
    assert typed.pick("lost", offered)["value"] == "c"
    assert typed.pick("I actually need a trade license for my new shop in Bole", offered) is None
    single = {"widget": "choice", "chips": [], "options": offered["options"][:1]}
    assert typed.pick("yes", single)["value"] == "a"


def test_text_it_does_not_understand_never_ends_or_restarts_the_conversation(client):
    p = _turn(client, message="asdkjh qwe")
    assert p["reply"]["intent"] not in ("goodbye", "start_over")
    assert "Good luck" not in p["reply"]["text"]
    assert not p["reply"]["widget"]  # no random services to pick from


def test_a_service_we_do_not_cover_is_said_plainly_not_swapped_for_another(client):
    for message in ("how to get driving license in addis", "we want to register our marriage"):
        reply = _turn(client, message=message)["reply"]
        assert "in my guide yet" in reply["text"], message
        assert not reply["widget"], message
        assert message not in reply["text"]  # a whole sentence is not parroted back


def test_opening_a_cafe_in_amharic_gets_the_start_up_steps(client):
    reply = _turn(client, message="ካፌ መክፈት እፈልጋለሁ ምን ያስፈልገኛል")["reply"]
    assert reply["intent"] == "start_business"
    assert "ቲን" in reply["text"] or "TIN" in reply["text"]


def test_plc_or_sole_proprietor_gets_the_forms_explained_with_the_boundary(client):
    reply = _turn(client, message="should i register as PLC or sole proprietor")["reply"]
    assert reply["intent"] == "business_forms"
    for part in ("Sole proprietor", "one-member PLC", "1243/2021", "not legal or tax advice"):
        assert part in reply["text"]


def test_a_tax_rules_question_gets_the_tax_basics_not_one_service_fee(client):
    for message in ("when do i pay my annual tax", "do i need to register for VAT"):
        reply = _turn(client, message=message)["reply"]
        assert reply["intent"] == "tax_rules", message
        assert "15%" in reply["text"] and "not tax advice" in reply["text"]
        assert "VAT registration" in [q["label"] for q in reply["quick_replies"]]


def test_asking_for_an_accountant_does_not_turn_into_account_opening(client):
    p = _turn(client, message="I need an accountant to do my books")
    assert p["reply"]["intent"] == "hire_agent"
    assert not p["service"]
