"""Mission control's aggregate (operator-experience.md §2): `GET /organizations/{id}/pulse` —
the org pulse header numbers plus one overlay row per node."""

from __future__ import annotations


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _root_of(org: dict) -> dict:
    return next(a for a in org["agents"] if a["managerId"] is None)


def _seed_live_actuation(actuation_id: str, org_id: str) -> None:
    from canopy_server.deps import get_db, now_iso

    ts = now_iso()
    with get_db().transaction() as conn:
        conn.execute(
            "INSERT INTO actuation (id, org_id, state, created_at, updated_at) VALUES (?,?,?,?,?)",
            (actuation_id, org_id, "live", ts, ts),
        )


def test_pulse_idle_org(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    p = client.get(f"/api/organizations/{org['id']}/pulse").json()
    assert p["actuation"] is None
    assert p["intents"] == {"open": 0, "total": 0}
    assert p["gates"] == {"open": 0, "byKind": {}, "attention": 0}
    assert p["burn"]["tokensPerMinute"] == 0
    [node] = p["nodes"]
    assert node["status"] == "not-actuated" and node["current"] is None
    assert node["queueDepth"] == 0 and node["wip"] == 0 and node["runtimeKind"]

    assert client.get("/api/organizations/nope/pulse").status_code == 404


def test_pulse_live_overlay(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])

    a = client.post(
        f"/api/organizations/{org['id']}/intents",
        json={"text": "Add CSV export; all tests must pass", "targetNodeId": root["id"]},
    ).json()["assignment"]

    # Briefed = queued: depth 1, wip 1, nothing current yet.
    p = client.get(f"/api/organizations/{org['id']}/pulse").json()
    assert p["actuation"]["state"] == "live"
    assert p["intents"] == {"open": 1, "total": 1}
    [node] = p["nodes"]
    assert node["queueDepth"] == 1 and node["wip"] == 1 and node["current"] is None

    # Start executing with one settled step: current + meter + burn all move.
    client.post("/api/dp/assignment/events", headers=_h(s["token"]),
                json={"assignmentId": a["id"], "kind": "intake-complete"})
    client.post("/api/dp/plan", headers=_h(s["token"]),
                json={"assignmentId": a["id"], "stages": [{"title": "implement"}]})
    client.post("/api/dp/assignment/events", headers=_h(s["token"]), json={
        "assignmentId": a["id"], "kind": "step", "inputTokens": 120, "outputTokens": 60,
        "durationMs": 500, "deltaKind": "progress", "settle": True,
    })

    p = client.get(f"/api/organizations/{org['id']}/pulse?windowMinutes=60").json()
    [node] = p["nodes"]
    assert node["current"]["assignmentId"] == a["id"]
    assert node["current"]["state"] == "executing"
    assert node["current"]["briefPreview"].startswith("Add CSV export")
    # F15: the living plan's stage progress rides the pulse — the honest progress number.
    assert node["current"]["stageProgress"] == {"done": 0, "total": 1}
    assert node["queueDepth"] == 0 and node["wip"] == 1
    assert node["meter"]["spent"] == 180
    assert p["burn"]["tokensPerMinute"] == 180 / 60

    client.post("/api/dp/assignment/events", headers=_h(s["token"]),
                json={"assignmentId": a["id"], "kind": "stage-update", "stageIdx": 0,
                      "stageState": "done"})
    p = client.get(f"/api/organizations/{org['id']}/pulse").json()
    assert p["nodes"][0]["current"]["stageProgress"] == {"done": 1, "total": 1}

    # An operator-owned gate shows up in the header counts and on the node, owner-tagged
    # (F5: the UI tones operator work apart from internal wiring).
    client.post(f"/api/assignments/{a['id']}/intervene", json={"note": "hold on"})
    p = client.get(f"/api/organizations/{org['id']}/pulse").json()
    assert p["gates"]["open"] == 1
    assert p["gates"]["byKind"] == {"intervention": 1}
    assert p["gates"]["attention"] == 1
    assert p["nodes"][0]["openGateKinds"] == ["intervention"]
    assert p["nodes"][0]["openGates"] == [{"kind": "intervention", "owner": "operator"}]
