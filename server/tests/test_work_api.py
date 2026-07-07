"""Work API over HTTP — operator intents/assignments (engine.md §6) + the run-token data plane
(engine.md §5). Drives an assignment intent → plan → step → artifact → deliverable end to end."""

from __future__ import annotations

import base64


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _root_of(org: dict) -> dict:
    return next(a for a in org["agents"] if a["managerId"] is None)


def _seed_live_actuation(actuation_id: str, org_id: str) -> None:
    """Simulate an actuated org without booting subprocess agents: a live actuation row is all the
    operator intent endpoint reads (via actuator.get_current)."""
    from canopy_server.deps import get_db, now_iso

    ts = now_iso()
    with get_db().transaction() as conn:
        conn.execute(
            "INSERT INTO actuation (id, org_id, state, created_at, updated_at) VALUES (?,?,?,?,?)",
            (actuation_id, org_id, "live", ts, ts),
        )


def test_submit_intent_requires_actuation(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    r = client.post(f"/api/organizations/{org['id']}/intents", json={"text": "do it"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "NOT_ACTUATED"

    assert client.post("/api/organizations/nope/intents", json={"text": "x"}).status_code == 404


def test_intent_to_deliverable_over_http(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])

    # Operator submits the intent → root assignment is created and funded.
    r = client.post(
        f"/api/organizations/{org['id']}/intents",
        json={"text": "Add CSV export", "targetNodeId": root["id"]},
    )
    assert r.status_code == 201, r.text
    a = r.json()["assignment"]
    intent_id = r.json()["intent"]["id"]
    assert a["state"] == "briefed" and a["nodeId"] == root["id"]

    # The node's runtime sees its assignment.
    cur = client.get("/api/dp/assignment/current", headers=_h(s["token"])).json()
    assert cur["assignment"]["id"] == a["id"]
    assert cur["brief"]["text"] == "Add CSV export"
    assert cur["contract"] == {"kind": "artifact", "type": "Deliverable"}

    # intake → plan → step → artifact → finish, all over the data plane.
    assert client.post("/api/dp/assignment/events", headers=_h(s["token"]),
                       json={"assignmentId": a["id"], "kind": "intake-complete"}).status_code == 200
    pr = client.post("/api/dp/plan", headers=_h(s["token"]),
                     json={"assignmentId": a["id"], "stages": [{"title": "implement"}]})
    assert pr.status_code == 200 and pr.json()["version"] == 1
    assert client.get("/api/dp/assignment/current",
                      headers=_h(s["token"])).json()["assignment"]["state"] == "executing"

    step = client.post("/api/dp/assignment/events", headers=_h(s["token"]), json={
        "assignmentId": a["id"], "kind": "step", "inputTokens": 120, "outputTokens": 60,
        "durationMs": 800, "deltaKind": "progress", "stageIdx": 0,
    })
    assert step.status_code == 200

    payload = base64.b64encode(b"col1,col2\n1,2\n").decode()
    put = client.post("/api/dp/artifacts", headers=_h(s["token"]), json={
        "assignmentId": a["id"], "name": "csv-export", "type": "code-patch",
        "contentBase64": payload,
    })
    assert put.status_code == 200, put.text
    ref = put.json()["ref"]
    got = client.get(f"/api/dp/artifacts?ref={ref}", headers=_h(s["token"]))
    assert got.status_code == 200 and got.json()["contentBase64"] == payload

    fin = client.post("/api/dp/finish", headers=_h(s["token"]),
                      json={"assignmentId": a["id"], "refs": [ref], "summary": "done"})
    assert fin.status_code == 200 and fin.json()["artifactRefs"] == [ref]

    # Operator drill-downs reflect the whole trail.
    detail = client.get(f"/api/assignments/{a['id']}").json()
    assert detail["assignment"]["state"] == "delivering"
    assert detail["deliverable"]["summary"] == "done"
    assert len(detail["steps"]) == 1 and detail["plan"]["stages"][0]["title"] == "implement"
    assert detail["meter"]["id"] == a["meterId"]

    idet = client.get(f"/api/intents/{intent_id}").json()
    assert idet["intent"]["rootAssignmentId"] == a["id"]
    assert len(idet["assignments"]) == 1

    lst = client.get(f"/api/organizations/{org['id']}/assignments?node={root['id']}").json()
    assert [x["id"] for x in lst["assignments"]] == [a["id"]]


def test_data_plane_rejects_foreign_assignment(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    other = mint_session(org["id"], node_id="a_intruder")  # a different node's run token

    from canopy_server.deps import get_engine

    a = get_engine().submit_intent(
        org["id"], s["actuationId"], "mine", target_node=root["id"]
    ).assignment

    r = client.post("/api/dp/plan", headers=_h(other["token"]),
                    json={"assignmentId": a.id, "stages": [{"title": "steal"}]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_YOUR_ASSIGNMENT"

    missing = client.post("/api/dp/assignment/events", headers=_h(s["token"]),
                          json={"assignmentId": "as_nope", "kind": "intake-complete"})
    assert missing.status_code == 404
