"""The canopy-agent `loop` runtime, driven against the real control plane over ASGI.

Imports the actual agent loop code (no subprocess) and ticks it through one assignment:
briefed -> planning -> executing -> delivering, producing a real artifact + deliverable and a
metered Step. Proves E1 item 4 wires through the data plane (item 3) into the engine + ledger +
artifact store (items 1-2), including the unified Step (work_step id == SpendEvent step_id).
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from fastapi.testclient import TestClient

# The runtime lives in the separate canopy-agent package (never importing canopy_server).
_AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))

from canopy_agent.runtime import AgentConfig, loop_tick  # noqa: E402


def _root_of(team: dict) -> dict:
    return next(a for a in team["agents"] if a["managerId"] is None)


def test_loop_runtime_drives_intent_to_deliverable(client, make_org, mint_session):
    from canopy_server.deps import get_db, get_engine

    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(team)
    s = mint_session(team["id"], node_id=root["id"])
    a = get_engine().submit_intent(
        team["id"], s["actuationId"], "Add CSV export to the report endpoints",
        target_node=root["id"],
    ).assignment

    from canopy_server.main import app

    cfg = AgentConfig(
        cp_url="http://cp", run_token=s["token"], node_id=root["id"],
        actuation_id=s["actuationId"], a2a_host="127.0.0.1", a2a_port=0,
    )
    # A sync TestClient with the run token stands in for the agent's httpx.Client — same
    # .get/.post(json=...) surface the loop uses, backed by the same in-process app.
    agent = TestClient(app, headers={"Authorization": f"Bearer {s['token']}"})

    statuses = []
    for _ in range(6):  # briefed->planning->executing->delivering needs three advancing ticks
        statuses.append(loop_tick(agent, cfg))
        if client.get(f"/api/assignments/{a.id}").json()["assignment"]["state"] == "delivering":
            break

    detail = client.get(f"/api/assignments/{a.id}").json()
    assert detail["assignment"]["state"] == "delivering"
    assert "engaged" in statuses
    assert loop_tick(agent, cfg) == "idle"  # work done; nothing left to drive

    # A real deliverable with one artifact, whose content came from the brief.
    deliverable = detail["deliverable"]
    assert deliverable["kind"] == "artifact" and len(deliverable["artifactRefs"]) == 1
    ref = deliverable["artifactRefs"][0]
    got = agent.get(f"/api/dp/artifacts?ref={ref}").json()
    assert b"CSV export" in base64.b64decode(got["contentBase64"])

    # Spend landed on the assignment's own meter, and the Step is unified with the SpendEvent.
    assert detail["meter"]["spent"] > 0
    art_step = next(st for st in detail["steps"] if st["deltaKind"] == "artifact")
    with get_db().connect() as conn:
        row = conn.execute(
            "SELECT step_id FROM ledger_spend_event WHERE step_id=?", (art_step["id"],)
        ).fetchone()
    assert row is not None  # work_step.id == ledger SpendEvent.step_id (one Step, two views)


def test_loop_manager_fans_out_and_synthesizes(client, make_org, mint_session):
    """The E3.6 mock-manager tick (amendments §3.3): a whole pod runs the delegation flow on
    the loop spine — staged fan-out, operator approval, IC work, per-delivery review wakes,
    and the lead's synthesized deliverable closing the intent."""
    from canopy_agent.runtime import AgentConfig, loop_tick

    from canopy_server.deps import get_engine
    from canopy_server.main import app

    team = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    by_role = {a["role"]["key"]: a for a in team["agents"]}
    lead = by_role["engineering-lead"]
    ics = [by_role["backend-engineer"], by_role["frontend-engineer"], by_role["qa-engineer"]]
    s_lead = mint_session(team["id"], node_id=lead["id"])
    sessions = {lead["id"]: s_lead}
    for ic in ics:
        sessions[ic["id"]] = mint_session(team["id"], node_id=ic["id"],
                                          actuation_id=s_lead["actuationId"])
    # Charters over HTTP need actuation rows; the loop's charter fetch tolerates a 404 and
    # would treat the lead as an IC — so seed real charters for everyone.
    from test_cli_runtime import _seed_charter

    for node_id in sessions:
        _seed_charter(team, s_lead["actuationId"], node_id)

    eng = get_engine()
    root = eng.submit_intent(team["id"], s_lead["actuationId"],
                             "ship the CSV export feature", target_node=lead["id"]).assignment

    def agent(node_id):
        return TestClient(app, headers={"Authorization":
                                        f"Bearer {sessions[node_id]['token']}"})

    def cfg(node_id):
        return AgentConfig(cp_url="http://cp", run_token=sessions[node_id]["token"],
                           node_id=node_id, actuation_id=s_lead["actuationId"],
                           a2a_host="127.0.0.1", a2a_port=0)

    def tick_all():
        loop_tick(agent(lead["id"]), cfg(lead["id"]))
        for ic in ics:
            loop_tick(agent(ic["id"]), cfg(ic["id"]))

    # Drive the team; approve the lead's staged fan-out when the plan-review gate appears.
    for _ in range(20):
        tick_all()
        gates = client.get(
            f"/api/teams/{team['id']}/gates?state=open&owner=operator"
        ).json()["gates"]
        for g in gates:
            if g["kind"] == "approval":
                client.post(f"/api/gates/{g['id']}/resolve", json={"action": "approve"})
        if client.get(f"/api/assignments/{root.id}").json()["assignment"]["state"] \
                == "delivering":
            break

    detail = client.get(f"/api/assignments/{root.id}").json()
    assert detail["assignment"]["state"] == "delivering"  # the lead synthesized and finished
    children = client.get(
        f"/api/teams/{team['id']}/assignments"
    ).json()["assignments"]
    child_rows = [c for c in children if c["parentId"] == root.id]
    assert len(child_rows) == 3 and all(c["state"] == "closed" for c in child_rows)

    # Operator accepts the root: intent completed, every meter accounted.
    client.post(f"/api/assignments/{root.id}/accept", json={"note": "ship it"})
    intent = client.get(f"/api/intents/{root.intentId}").json()["intent"]
    assert intent["state"] == "completed"
