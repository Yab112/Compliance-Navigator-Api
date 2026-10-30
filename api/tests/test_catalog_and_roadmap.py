from conftest import API

from services.keyword_chat import _detect_goal, _detect_held


def test_catalog_search_and_detail(client):
    r = client.get(f"{API}/catalog/services", params={"q": "passport", "limit": 5}).json()["payload"]
    assert r["total"] > 0
    detail = client.get(f"{API}/catalog/services/{r['items'][0]['id']}")
    assert detail.status_code == 200
    assert client.get(f"{API}/catalog/services/nope").status_code == 404


def test_roadmap_steps_carry_mesob_info(client):
    r = client.post(f"{API}/roadmaps", json={"goal": "trade_license", "subCity": "bole", "documentsHeld": []})
    steps = r.json()["payload"]["roadmap"]["steps"]
    tin = next(s for s in steps if s["id"] == "tin")
    assert tin["mesob"]["serviceName"].startswith("Taxpayer Identification Number")


def test_keyword_goal_ignores_documents_already_held():
    text = "I want a trade license in Bole, I already have my kebele ID"
    assert _detect_goal(text) == "trade_license"
    assert _detect_held(text) == ["kebele_id"]
    assert _detect_held("I need a passport") == []


def test_org_office_in_another_sub_city_is_not_used(monkeypatch):
    from services.org_service import paths

    snap = {"name": "Resident ID card", "slug": "resident-id", "outputs": [{"document_id": "kebele_id"}],
            "org": {"id": "o1", "name": "Bole Woreda 03", "slug": "bole-w03"}}
    monkeypatch.setattr(paths, "_live_services", lambda: {"s1": snap})
    monkeypatch.setattr(paths, "_service_branches", lambda s: [{"name": "Woreda 03", "sub_city": "bole"}])
    monkeypatch.setattr(paths, "_issuer_index", lambda live: {})
    monkeypatch.setattr(paths, "_freshness_and_changes", lambda sid: {
        "confirmed_at": None, "confirmed_days_ago": None, "confirmation_due": False, "upcoming_change": None})
    assert paths.org_data_for_steps(["kebele_id"], "yeka") == {}
    assert paths.org_data_for_steps(["kebele_id"], "bole")["kebele_id"]["orgName"] == "Bole Woreda 03"


def test_path_offices_match_sub_city_and_hide_stand_in_data(client):
    from services.roadmap_service import generate_roadmap

    steps = generate_roadmap("trade_license", "yeka", [])["steps"]
    for s in steps:
        assert "Bole" not in s["issuingAuthority"], s
        assert "Bole" not in ((s.get("orgService") or {}).get("orgName") or "")
        for phone in (s.get("office") or {}).get("phones", []):
            assert "000 000" not in phone
    kebele = next(s for s in steps if s["id"] == "kebele_id")
    assert "woreda office" in kebele["office"]["note"] and "Yeka" in kebele["office"]["note"]


def test_saved_path_drops_an_org_office_that_no_longer_applies(monkeypatch):
    from services import org_service, roadmap_service

    org = {"orgName": "Bole Woreda 03 (sample)", "isFree": False, "feeAmountMin": 50, "feeCurrency": "ETB",
           "paymentMethods": ["Cash"], "requirements": [], "rejectionReasons": [], "legalBasis": None, "confirmedAt": None}
    step = {"id": "kebele_id", "title": "Kebele ID", "issuingAuthority": "Local Kebele Office", "feeEtb": 0,
            "paymentMethods": ["cash"], "requiredInputs": ["Birth certificate"], "rejectionReasons": [],
            "office": {"name": "Yeka Sub-city Kebele Office", "phones": ["+251 11 000 0000", "+251 11 662 7688"]}}
    roadmap = {"request": {"subCity": "yeka"}, "steps": [step]}
    monkeypatch.setattr(org_service, "org_data_for_steps", lambda ids, sc: {"kebele_id": org})
    roadmap_service._attach_org_data(roadmap)
    assert step["issuingAuthority"] == org["orgName"] and step["feeEtb"] == 50
    assert step["office"]["phones"] == ["+251 11 662 7688"]
    monkeypatch.setattr(org_service, "org_data_for_steps", lambda ids, sc: {})
    roadmap_service._attach_org_data(roadmap)
    assert step["issuingAuthority"] == "Local Kebele Office" and step["feeEtb"] == 0
    assert "orgService" not in step and "graphDefaults" not in step


def test_catalog_names_and_summary_are_readable():
    from services import catalog_service

    s = catalog_service.get_service("mesob-728")
    assert s["name"] == "Renewal passport"
    assert s["summary"] == "At ICS: official fee 21,000 ETB, about 5 days"
    assert catalog_service.display_name("RENEWAL EOID (YELLOW CARD)") == "Renewal EOID (yellow card)"
    assert catalog_service.display_name("Approval of eSW User") == "Approval of eSW User"
