"""The agent inspector surface (engine.md §6, operator-experience.md §3):
`GET /organizations/{id}/agents/{nodeId}/state` aggregate + memory get/reset + workspace
file preview. Drives a real assignment over the data plane, then reads it all back from the
operator side."""

from __future__ import annotations

from pathlib import Path


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


def _drive_to_delivering(client, s: dict, assignment_id: str) -> None:
    """intake → plan → one settled step (lands a real SpendEvent) → finish."""
    import base64

    client.post("/api/dp/assignment/events", headers=_h(s["token"]),
                json={"assignmentId": assignment_id, "kind": "intake-complete"})
    client.post("/api/dp/plan", headers=_h(s["token"]),
                json={"assignmentId": assignment_id, "stages": [{"title": "implement"}]})
    r = client.post("/api/dp/assignment/events", headers=_h(s["token"]), json={
        "assignmentId": assignment_id, "kind": "step", "inputTokens": 100, "outputTokens": 50,
        "durationMs": 500, "deltaKind": "progress", "stageIdx": 0, "settle": True,
    })
    assert r.status_code == 200, r.text
    put = client.post("/api/dp/artifacts", headers=_h(s["token"]), json={
        "assignmentId": assignment_id, "name": "out", "type": "code-patch",
        "contentBase64": base64.b64encode(b"done\n").decode(),
    })
    client.post("/api/dp/finish", headers=_h(s["token"]),
                json={"assignmentId": assignment_id, "refs": [put.json()["ref"]],
                      "summary": "done"})


def test_agent_state_aggregate(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])

    a = client.post(
        f"/api/organizations/{org['id']}/intents",
        json={"text": "Add CSV export", "targetNodeId": root["id"]},
    ).json()["assignment"]

    # Freshly briefed = queued, nothing current yet.
    st = client.get(f"/api/organizations/{org['id']}/agents/{root['id']}/state").json()
    assert st["nodeId"] == root["id"]
    assert st["charter"]["roleKey"] == "engineering-lead"
    assert st["charter"]["instructions"]
    assert st["binding"]["provider"] == "mock"
    assert st["salary"]["perAssignmentAllowance"] > 0
    assert isinstance(st["envelope"]["toolGrants"], list) and st["envelope"]["runtimeKind"]
    assert st["actuation"] == {"id": s["actuationId"], "state": "live"}
    assert st["current"] is None
    assert [q["id"] for q in st["queue"]] == [a["id"]]
    assert st["stats"]["assignmentsTotal"] == 1 and st["stats"]["assignmentsDone"] == 0

    # Work it to delivering: it becomes current, with plan + steps + meter in the drill-down.
    _drive_to_delivering(client, s, a["id"])
    st = client.get(f"/api/organizations/{org['id']}/agents/{root['id']}/state").json()
    assert st["current"]["assignment"]["id"] == a["id"]
    assert st["current"]["plan"]["stages"][0]["title"] == "implement"
    assert len(st["current"]["steps"]) == 1
    assert st["queue"] == []
    assert st["spend"]["nodeTokens"] == 150
    assert st["spend"]["sharePct"] == 100.0

    # Accept: history gains the row (with its spend), stats read 1-for-1 accepted.
    client.post(f"/api/assignments/{a['id']}/accept", json={"note": "ship it"})
    st = client.get(f"/api/organizations/{org['id']}/agents/{root['id']}/state").json()
    assert st["current"] is None
    assert st["stats"]["assignmentsDone"] == 1
    assert st["stats"]["acceptanceRate"] == 1.0
    assert st["stats"]["avgCostTokens"] == 150
    assert st["history"][0]["id"] == a["id"] and st["history"][0]["spentTokens"] == 150
    # Accepting wrote the close-out memory entry; the aggregate carries it.
    assert st["memory"] and st["memory"][-1]["entry"]["outcome"] == "accepted"


def test_agent_state_404s(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    assert client.get("/api/organizations/nope/agents/a_x/state").status_code == 404
    r = client.get(f"/api/organizations/{org['id']}/agents/a_ghost/state")
    assert r.status_code == 404


def test_memory_get_and_reset(client, make_org):
    from canopy_server.deps import get_activity, get_work_store

    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    get_work_store().append_memory(org["id"], root["id"], {"outcome": "accepted", "n": 1})

    url = f"/api/organizations/{org['id']}/agents/{root['id']}/memory"
    assert [e["entry"]["n"] for e in client.get(url).json()["entries"]] == [1]

    assert client.delete(url).json() == {"reset": True}
    assert client.get(url).json()["entries"] == []
    # The wipe is audited (and therefore rides the SSE activity stream).
    kinds = [e["kind"] for e in get_activity().list(org["id"])]
    assert "memory.reset" in kinds


def test_workspace_listing_and_preview(client, make_org, mint_session, tmp_path):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])

    # No sandbox on disk yet → no workspace, and the preview 404s.
    st = client.get(f"/api/organizations/{org['id']}/agents/{root['id']}/state").json()
    assert st["workspace"] is None
    base = f"/api/organizations/{org['id']}/agents/{root['id']}/workspace/file"
    assert client.get(f"{base}?path=out/x.txt").status_code == 404

    # Materialize what the sandbox would have created (CANOPY_DATA_DIR is tmp_path).
    ws = Path(tmp_path) / "sandboxes" / s["actuationId"] / root["id"] / "workspace"
    (ws / "out").mkdir(parents=True)
    (ws / "out" / "result.txt").write_text("col1,col2\n1,2\n", encoding="utf-8", newline="\n")
    (ws / "out" / "blob.bin").write_bytes(b"\x00\x01\x02")
    secret = Path(tmp_path) / "sandboxes" / "secret.txt"
    secret.write_text("no", encoding="utf-8")

    st = client.get(f"/api/organizations/{org['id']}/agents/{root['id']}/state").json()
    paths = {f["path"] for f in st["workspace"]["files"]}
    assert paths == {"out/result.txt", "out/blob.bin"}
    assert st["workspace"]["truncated"] is False

    r = client.get(f"{base}?path=out/result.txt").json()
    assert r["content"] == "col1,col2\n1,2\n" and r["reason"] is None

    assert client.get(f"{base}?path=out/blob.bin").json()["reason"] == "binary"
    assert client.get(f"{base}?path=../../secret.txt").status_code == 422


def test_best_actuation_prefers_live_then_newest_existing_sandbox(client):
    """F12: after a re-actuation, the inspector reads the newest sandbox that exists on
    disk — not the (oldest) assignment's original actuationId."""
    from types import SimpleNamespace

    from canopy_server.config import get_data_dir
    from canopy_server.routes.inspector import _best_actuation

    node = "a_n1"
    for act in ("act_old", "act_new"):
        (get_data_dir() / "sandboxes" / act / node).mkdir(parents=True, exist_ok=True)
    assignments = [
        SimpleNamespace(actuationId="act_old", updatedAt="2026-01-01T00:00:00Z"),
        SimpleNamespace(actuationId="act_new", updatedAt="2026-02-01T00:00:00Z"),
    ]
    # Live actuation always wins.
    assert _best_actuation("act_new", assignments, node) == "act_new"
    # Deactuated: newest assignment's actuation with an existing sandbox.
    assert _best_actuation(None, assignments, node) == "act_new"
    # A live id with no sandbox yet falls through to the newest existing one.
    assert _best_actuation("act_ghost", assignments, node) == "act_new"
    # Nothing on disk at all: first candidate, so the caller still has a path to show.
    assert _best_actuation(None, [assignments[0]], "a_other") == "act_old"
