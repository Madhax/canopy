"""E6 hardening vectors (mvp.md): the failure-and-recovery semantics of engine.md §8 —
step redelivery never double-charges, the control plane restarting mid-intent loses nothing,
and deactuate → re-actuate continues open work (the position owns its work, like memory)."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient


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


def _stop_actuation(actuation_id: str) -> None:
    from canopy_server.deps import get_db, now_iso

    with get_db().transaction() as conn:
        conn.execute(
            "UPDATE actuation SET state='stopped', updated_at=? WHERE id=?",
            (now_iso(), actuation_id),
        )


def _to_executing(client, s: dict, assignment_id: str) -> None:
    client.post("/api/dp/assignment/events", headers=_h(s["token"]),
                json={"assignmentId": assignment_id, "kind": "intake-complete"})
    client.post("/api/dp/plan", headers=_h(s["token"]),
                json={"assignmentId": assignment_id, "stages": [{"title": "implement"}]})


def _settled_step(client, token: str, assignment_id: str, step_id: str) -> int:
    r = client.post("/api/dp/assignment/events", headers=_h(token), json={
        "assignmentId": assignment_id, "kind": "step", "inputTokens": 100, "outputTokens": 50,
        "durationMs": 400, "deltaKind": "progress", "stepId": step_id, "settle": True,
    })
    return r.status_code


def test_step_redelivery_never_double_charges(client, make_org, mint_session):
    """AR-3 end to end over HTTP: a redelivered step report (same step id) is one Step, one
    SpendEvent, one charge."""
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])
    a = client.post(
        f"/api/organizations/{org['id']}/intents",
        json={"text": "Add CSV export", "targetNodeId": root["id"]},
    ).json()["assignment"]
    _to_executing(client, s, a["id"])

    assert _settled_step(client, s["token"], a["id"], "st_redelivered") == 200
    assert _settled_step(client, s["token"], a["id"], "st_redelivered") == 200  # the redelivery

    detail = client.get(f"/api/assignments/{a['id']}").json()
    assert len(detail["steps"]) == 1
    assert detail["meter"]["spent"] == 150

    from canopy_server.deps import get_db

    with get_db().connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM ledger_spend_event WHERE step_id='st_redelivered'"
        ).fetchone()["n"]
    assert n == 1


def test_control_plane_restart_mid_intent(tmp_path, monkeypatch):
    """Work state is SQLite; loops are stateless (engine.md §8). Kill the app mid-intent,
    start a fresh one over the same data dir: nothing is lost, redelivery still dedupes, and
    the intent runs to acceptance."""
    monkeypatch.setenv("CANOPY_DATA_DIR", str(tmp_path))
    from canopy_server.main import app

    with TestClient(app) as c1:
        org = c1.post(
            "/api/organizations",
            json={"name": "Acme", "organizationType": "product-engineering",
                  "seed": {"kind": "root", "roleKey": "engineering-lead"}},
        ).json()
        root = _root_of(org)

        from canopy_server.deps import get_ledger, get_profile_store, get_runtokens
        from canopy_server.ids import new_actuation_id
        from canopy_server.profiles import ProfileParams

        profiles = get_profile_store()
        profile = profiles.create_profile(
            org["id"], name="p", provider="mock", model="mock-1",
            api_key_secret_id=None, params=ProfileParams(maxOutputTokens=4096),
        )
        profiles.set_binding(org["id"], root["id"], profile.id)
        actuation_id = new_actuation_id()
        meter = get_ledger().open_meter(actuation_id, root["id"], 5000)
        token, _ = get_runtokens().issue(
            actuation_id, root["id"], org["id"], default_meter_id=meter.id
        )
        _seed_live_actuation(actuation_id, org["id"])

        a = c1.post(
            f"/api/organizations/{org['id']}/intents",
            json={"text": "Add CSV export", "targetNodeId": root["id"]},
        ).json()["assignment"]
        _to_executing(c1, {"token": token}, a["id"])
        assert _settled_step(c1, token, a["id"], "st_before_crash") == 200

    # "Restart": drop every cached singleton so the next app builds fresh objects over the
    # same on-disk state — the honest simulation of a new process.
    import canopy_server.config as config
    import canopy_server.deps as deps

    for mod in (deps, config):
        for name in dir(mod):
            fn = getattr(mod, name)
            if hasattr(fn, "cache_clear"):
                fn.cache_clear()

    with TestClient(app) as c2:
        detail = c2.get(f"/api/assignments/{a['id']}").json()
        assert detail["assignment"]["state"] == "executing"
        assert detail["meter"]["spent"] == 150
        assert detail["plan"]["stages"][0]["title"] == "implement"

        # An in-flight report redelivered across the restart still dedupes (step-id idempotency).
        assert _settled_step(c2, token, a["id"], "st_before_crash") == 200
        assert c2.get(f"/api/assignments/{a['id']}").json()["meter"]["spent"] == 150

        # And the intent runs to the end on the new process.
        put = c2.post("/api/dp/artifacts", headers=_h(token), json={
            "assignmentId": a["id"], "name": "out", "type": "code-patch",
            "contentBase64": base64.b64encode(b"done\n").decode(),
        })
        c2.post("/api/dp/finish", headers=_h(token),
                json={"assignmentId": a["id"], "refs": [put.json()["ref"]], "summary": "done"})
        c2.post(f"/api/assignments/{a['id']}/accept", json={"note": ""})
        assert c2.get(f"/api/assignments/{a['id']}").json()["assignment"]["state"] == "closed"


def test_reactuation_continues_open_work(client, make_org, mint_session):
    """Deactuate with an assignment mid-flight, re-actuate, and the node picks up exactly
    where it left off: same assignment, same meter, same money — and durable memory written
    at close survives the actuation boundary (D5's doctrine: work belongs to the position)."""
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s1 = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s1["actuationId"], org["id"])

    a = client.post(
        f"/api/organizations/{org['id']}/intents",
        json={"text": "Add CSV export", "targetNodeId": root["id"]},
    ).json()["assignment"]
    _to_executing(client, s1, a["id"])
    assert _settled_step(client, s1["token"], a["id"], "st_act_one") == 200

    # Deactuate, then re-actuate: a NEW actuation, a NEW run token for the same position.
    _stop_actuation(s1["actuationId"])
    s2 = mint_session(org["id"], node_id=root["id"])
    assert s2["actuationId"] != s1["actuationId"]
    _seed_live_actuation(s2["actuationId"], org["id"])

    # The new session sees the same open assignment, on its original meter.
    cur = client.get("/api/dp/assignment/current", headers=_h(s2["token"])).json()
    assert cur["assignment"]["id"] == a["id"]
    assert cur["assignment"]["state"] == "executing"
    assert cur["meter"]["id"] == a["meterId"] and cur["meter"]["spent"] == 150

    # Work continues under the new actuation and settles into the same meter.
    assert _settled_step(client, s2["token"], a["id"], "st_act_two") == 200
    put = client.post("/api/dp/artifacts", headers=_h(s2["token"]), json={
        "assignmentId": a["id"], "name": "out", "type": "code-patch",
        "contentBase64": base64.b64encode(b"done\n").decode(),
    })
    assert put.status_code == 200, put.text
    ref = put.json()["ref"]
    # The grant wall is position-keyed too: the node still reads its own artifact.
    assert client.get(f"/api/dp/artifacts?ref={ref}", headers=_h(s2["token"])).status_code == 200

    client.post("/api/dp/finish", headers=_h(s2["token"]),
                json={"assignmentId": a["id"], "refs": [ref], "summary": "done"})
    client.post(f"/api/assignments/{a['id']}/accept", json={"note": "ship it"})
    detail = client.get(f"/api/assignments/{a['id']}").json()
    assert detail["assignment"]["state"] == "closed"
    assert detail["meter"]["spent"] == 300  # both actuations' steps, one meter

    from canopy_server.deps import get_work_store

    entries = get_work_store().get_memory(org["id"], root["id"])
    assert entries and entries[-1].entry["outcome"] == "accepted"
