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


def _root_of(org: dict) -> dict:
    return next(a for a in org["agents"] if a["managerId"] is None)


def test_loop_runtime_drives_intent_to_deliverable(client, make_org, mint_session):
    from canopy_server.deps import get_db, get_engine

    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    a = get_engine().submit_intent(
        org["id"], s["actuationId"], "Add CSV export to the report endpoints",
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
