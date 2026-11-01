"""The agentic assistant, with Claude's responses faked: tools run against our real data, every number
in a reply must come from a tool or the person, and anything wrong falls back to the templates."""

from types import SimpleNamespace as NS

import pytest

from assistant import llm_agent
from test_assistant import _turn


def _text(t):
    return NS(type="text", text=t, citations=None)


def _tool(name, args, i="t1"):
    return NS(type="tool_use", id=i, name=name, input=args)


def _resp(*blocks, stop="end_turn"):
    stop = "tool_use" if any(b.type == "tool_use" for b in blocks) and stop == "end_turn" else stop
    return NS(content=list(blocks), stop_reason=stop, model="claude-opus-5-5")


@pytest.fixture
def scripted(monkeypatch):
    """Plays a list of responses in order and records what the agent sent."""
    sent = []

    def play(responses):
        queue = list(responses)
        monkeypatch.setattr(llm_agent, "enabled", lambda: True)

        def create(messages):
            sent.append([dict(m) for m in messages])
            return queue.pop(0)

        monkeypatch.setattr(llm_agent, "_create", create)
        return sent

    return play


def test_agent_looks_up_our_data_and_answers_with_its_numbers(client, scripted):
    sent = scripted([
        _resp(_tool("search_services", {"query": "commercial registration"})),
        _resp(_tool("business_guide", {"topics": ["costs"]}, "t2")),
        _resp(_text("Commercial registration is 1,200 ETB in our records, not yet confirmed by the office. "
                    "Pay only at the window.")),
    ])
    p = _turn(client, message="how much is commercial registration and what else do i pay to start")
    reply = p["reply"]
    assert reply["intent"] == "agentic"
    assert "1,200 ETB" in reply["text"]
    assert reply["agentic"]["tools"] == ["search_services", "business_guide"]
    # The tool results went back to the model as tool_result blocks
    assert any(m["role"] == "user" and isinstance(m["content"], list) and isinstance(m["content"][0], dict)
               and m["content"][0]["type"] == "tool_result" for m in sent[-1])


def test_an_invented_fee_is_sent_back_and_then_the_templates_answer(client, scripted):
    scripted([
        _resp(_text("A trade license costs 4,750 ETB.")),
        _resp(_text("A trade license costs 4,750 ETB, trust me.")),
    ])
    reply = _turn(client, message="how much is a trade license")["reply"]
    assert reply["intent"] != "agentic"
    assert "4,750" not in reply["text"]


def test_a_fixed_reply_after_the_check_is_accepted(client, scripted):
    sent = scripted([
        _resp(_text("Starting costs about 9,999 ETB.")),
        _resp(_text("I don't have a total in our records; each office sets its own fee.")),
    ])
    reply = _turn(client, message="what does it cost overall")["reply"]
    assert reply["intent"] == "agentic"
    assert "9,999" not in reply["text"]
    assert "[system check]" in str(sent[-1][-1]["content"])


def test_a_refusal_or_api_error_falls_back_to_the_templates(client, scripted, monkeypatch):
    scripted([_resp(_text(""), stop="refusal")])
    assert _turn(client, message="I need a passport")["reply"]["intent"] != "agentic"

    def boom(messages):
        raise RuntimeError("network down")

    monkeypatch.setattr(llm_agent, "_create", boom)
    reply = _turn(client, message="I need a passport")["reply"]
    assert reply["intent"] != "agentic" and reply["widget"]  # the passport choice, from the templates


def test_buttons_and_typed_picks_never_go_to_the_model(client, scripted, monkeypatch):
    monkeypatch.setattr(llm_agent, "enabled", lambda: False)
    p = _turn(client, message="I need a passport")  # templates: the passport choice
    sent = scripted([])  # now on; any model call would fail the turn
    p = _turn(client, conversation_id=p["conversationId"], message="new")
    assert p["reply"]["intent"] == "typed_choice"
    p = _turn(client, conversation_id=p["conversationId"], action={"type": "sub_city", "value": "bole"})
    assert p["subCity"] == "bole"
    assert sent == []


def test_grounding_ignores_list_numbers_and_accepts_law_numbers_from_tools():
    assert llm_agent.unsupported_numbers("1. TIN 2. Registration under 980/2016", ["Proclamation No. 980/2016"]) == set()
    assert llm_agent.unsupported_numbers("Pay 350 birr", ["fee 300"]) == {"350"}
