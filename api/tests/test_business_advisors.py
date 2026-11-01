"""Tax and business advisors: licences by specialty, where the work happens, and the assistant's
'I'm starting a business' and investment-advice answers."""

from conftest import API
from services.vetting.rules import document_kinds, licence_kinds
from test_assistant import _turn


def test_licence_kinds_follow_advisor_specialties():
    advisor = {"provider_type": "advisor", "entity_type": "individual", "specialties": ["tax_agent", "business_setup"]}
    assert licence_kinds(advisor) == ["tax_agent_licence"]
    assert "tax_agent_licence" in document_kinds(advisor)
    both = {**advisor, "specialties": ["auditor", "accountant"]}
    assert licence_kinds(both) == ["audit_licence", "accounting_qualification"]
    # Business set-up help needs no extra licence; other provider types never get these
    assert licence_kinds({**advisor, "specialties": ["business_setup"]}) == []
    assert licence_kinds({"provider_type": "agency", "entity_type": "company", "specialties": ["consultancy"]}) == []


def test_join_template_lists_the_licence_for_the_chosen_specialty(client):
    r = client.get(f"{API}/providers/vetting-requirements",
                   params={"entity": "individual", "type": "advisor", "specialties": "tax_agent"})
    assert r.status_code == 200, r.text
    kinds = [i.get("kind") for i in r.json()["payload"]["vetting"]["items"]]
    assert "tax_agent_licence" in kinds
    plain = client.get(f"{API}/providers/vetting-requirements", params={"entity": "individual"}).json()
    assert "tax_agent_licence" not in [i.get("kind") for i in plain["payload"]["vetting"]["items"]]


def test_start_business_gives_the_steps_with_source_and_boundary(client):
    p = _turn(client, message="I am about to start a new business but I am not sure what to do")
    reply = p["reply"]
    assert reply["intent"] == "start_business"
    text = reply["text"]
    for step in ("TIN", "commercial registration", "trade licence", "980/2016"):
        assert step in text
    assert "not legal or tax advice" in text
    labels = [q["label"] for q in reply["quick_replies"]]
    assert "Find a tax or business advisor" in labels


def test_a_message_naming_a_step_goes_to_that_step(client):
    p = _turn(client, message="how do I get a trade license for my new business")
    assert p["reply"]["intent"] != "start_business"


def test_start_business_in_amharic(client):
    p = _turn(client, message="አዲስ ንግድ መክፈት እፈልጋለሁ")
    assert p["reply"]["intent"] == "start_business"
    assert "980/2008" in p["reply"]["text"]


def test_no_investment_advice(client):
    p = _turn(client, message="which shares should I buy, should I invest in the stock market")
    assert p["reply"]["intent"] == "no_investment_advice"
    assert "Capital Market Authority" in p["reply"]["text"]


def test_asking_for_an_accountant_searches_advisors(client):
    p = _turn(client, message="I need an accountant for my shop")
    reply = p["reply"]
    assert reply["intent"] == "hire_agent"
    hrefs = [a.get("href") for a in reply.get("actions") or []]
    assert any(h and "type=advisor" in h and "specialty=accountant" in h for h in hrefs), hrefs


def test_advisor_joins_shows_licence_and_is_hired_at_the_clients_office(client, make_user):
    from test_providers import _admin, _join

    admin, user, customer = make_user("admin"), make_user(), make_user()
    base = dict(provider_type="advisor", display_name="Test Tax Advisor", service_ids=[],
                specialties=["tax_agent", "business_setup"], fee_from=1500, fee_unit="per_job")
    r = _join(client, user, **base)
    assert r.status_code == 400 and "where you work" in r.json()["detail"]
    r = _join(client, user, **base, delivery_modes=["online", "client_office"], visit_fee=300)
    assert r.status_code == 201, r.text
    p = r.json()["payload"]["provider"]
    assert p["delivery_modes"] == ["client_office", "online"]  # stored in a fixed order

    me = client.get(f"{API}/providers/me/vetting", headers=user["headers"])
    if me.status_code == 200:
        kinds = [i.get("kind") for i in me.json()["payload"]["vetting"]["items"]]
        assert "tax_agent_licence" in kinds

    assert _admin(client, admin, p["id"], "approve").status_code == 200
    public = client.get(f"{API}/providers/{p['slug']}").json()["payload"]["provider"]
    assert public["registration_no"].startswith("AD-")
    assert public["visit_fee"] == 300
    assert [lic["label"] for lic in public["licences"]] == ["Tax agent licence"]
    assert "reference_no" not in public["licences"][0]
    listing = client.get(f"{API}/providers", params={"type": "advisor", "specialty": "tax_agent"}).json()["payload"]
    assert any(i["id"] == p["id"] for i in listing["items"])

    hire = {"provider_id": p["slug"], "title": "File my first VAT return", "client_name": "Test Client",
            "client_phone": "0922000000", "client_telegram": "test_client"}
    r = client.post(f"{API}/hires", json=hire, headers=customer["headers"])
    assert r.status_code == 400 and "where you want to meet" in r.json()["detail"]
    r = client.post(f"{API}/hires", json={**hire, "delivery_mode": "provider_office"}, headers=customer["headers"])
    assert r.status_code == 400  # this advisor only visits or works online
    r = client.post(f"{API}/hires", json={**hire, "delivery_mode": "client_office"}, headers=customer["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["payload"]["hire"]["delivery_mode"] == "client_office"


def test_an_expired_licence_takes_the_advisor_off_the_list(client, make_user):
    from services import provider_service
    from services.db import execute
    from test_providers import _approved

    admin, user = make_user("admin"), make_user()
    p = _approved(client, admin, user, provider_type="advisor", display_name="Test Auditor", service_ids=[],
                  specialties=["auditor"], delivery_modes=["provider_office"])
    assert client.get(f"{API}/providers/{p['slug']}").status_code == 200
    execute("update provider_documents set expires_on = current_date - 1 "
            "where provider_id = %s and kind = 'audit_licence'", (p["id"],))
    provider_service.refresh_readiness(p["id"])
    assert client.get(f"{API}/providers/{p['slug']}").status_code == 404
