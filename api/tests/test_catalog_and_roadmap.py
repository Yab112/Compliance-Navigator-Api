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
