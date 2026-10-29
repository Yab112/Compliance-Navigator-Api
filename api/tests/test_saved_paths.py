"""Saved paths live on the server, belong to one account, and only that account can change them."""

from conftest import API


def _path(client, headers=None):
    r = client.post(f"{API}/roadmaps", json={"goal": "passport", "subCity": "bole", "documentsHeld": []},
                    headers=headers or {})
    assert r.status_code == 201, r.text
    return r.json()["payload"]["roadmap"]


def test_save_list_open_and_remove(client, make_user):
    me, other = make_user(), make_user()
    path = _path(client)  # made while signed out
    assert client.post(f"{API}/roadmaps/{path['id']}/save", headers=me["headers"]).status_code == 200
    items = client.get(f"{API}/roadmaps", headers=me["headers"]).json()["payload"]["items"]
    assert [i["id"] for i in items] == [path["id"]] and items[0]["steps"] == len(path["steps"])

    # Once saved, it is mine: others can't read, take over or change it
    assert client.get(f"{API}/roadmaps/{path['id']}", headers=me["headers"]).status_code == 200
    assert client.get(f"{API}/roadmaps/{path['id']}").status_code == 404
    assert client.get(f"{API}/roadmaps/{path['id']}", headers=other["headers"]).status_code == 404
    assert client.post(f"{API}/roadmaps/{path['id']}/save", headers=other["headers"]).status_code == 404
    step = path["steps"][0]["id"]
    assert client.patch(f"{API}/roadmaps/{path['id']}/steps/{step}", json={"completed": True},
                        headers=other["headers"]).status_code == 404
    assert client.patch(f"{API}/roadmaps/{path['id']}/steps/{step}", json={"completed": True},
                        headers=me["headers"]).status_code == 200
    assert client.get(f"{API}/roadmaps", headers=me["headers"]).json()["payload"]["items"][0]["completed"] == 1

    assert client.delete(f"{API}/roadmaps/{path['id']}", headers=other["headers"]).status_code == 404
    assert client.delete(f"{API}/roadmaps/{path['id']}", headers=me["headers"]).status_code == 200
    assert client.get(f"{API}/roadmaps", headers=me["headers"]).json()["payload"]["items"] == []


def test_paths_made_while_signed_in_are_listed(client, make_user):
    me = make_user()
    path = _path(client, me["headers"])
    assert [i["id"] for i in client.get(f"{API}/roadmaps", headers=me["headers"]).json()["payload"]["items"]] == [path["id"]]


def test_finishing_a_path_feedback(client, make_user):
    from services.db import fetch_all

    me = make_user()
    path = _path(client, me["headers"])
    steps = [s["id"] for s in path["steps"]]
    body = {"accuracy": 4, "days_taken": 12, "steps_different": [steps[0], "not-a-step"],
            "what_was_different": "[test] They also asked for a utility bill", "would_recommend": True}
    r = client.post(f"{API}/roadmaps/{path['id']}/feedback", json=body, headers=me["headers"])
    assert r.status_code == 201 and r.json()["payload"]["feedback"]["steps_different"] == [steps[0]]
    assert client.post(f"{API}/roadmaps/{path['id']}/feedback", json=body, headers=me["headers"]).status_code == 409
    got = client.get(f"{API}/roadmaps/{path['id']}/feedback", headers=me["headers"]).json()["payload"]["feedback"]
    assert got["accuracy"] == 4 and got["days_taken"] == 12
    flags = fetch_all("select target_id from feedback_flags where message like %s", ("%utility bill%",))
    assert [f["target_id"] for f in flags] == [steps[0]]  # the data team sees what differed
    other = make_user()
    assert client.post(f"{API}/roadmaps/{path['id']}/feedback", json=body, headers=other["headers"]).status_code == 404
