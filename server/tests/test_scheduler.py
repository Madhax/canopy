"""The portfolio governor (design/organizations/04, milestone C4).

The done-bar (07 §1): kill a mock window mid-run — sessions hold at the turn boundary
behind a capacity gate (`opened_by='trigger:capacity'`, scheduled waiting, not a stall),
and auto-resume when the scripted reset passes. Plus: pause/resume a team, the admission
table, active hours, and the degrade-model rung.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

from canopy_server.scheduler import in_active_hours

_AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))

from canopy_agent.runtime import AgentConfig, loop_tick  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _fleet(client, make_org, mint_session):
    from canopy_server.deps import get_engine
    from canopy_server.main import app

    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = next(a for a in team["agents"] if a["managerId"] is None)
    s = mint_session(team["id"], node_id=root["id"])
    a = get_engine().submit_intent(team["id"], s["actuationId"], "write the report",
                                   target_node=root["id"]).assignment
    agent = TestClient(app, headers={"Authorization": f"Bearer {s['token']}"})
    cfg = AgentConfig(cp_url="http://cp", run_token=s["token"], node_id=root["id"],
                      actuation_id=s["actuationId"], a2a_host="127.0.0.1", a2a_port=0)
    return team, root, s, a, agent, cfg


def _state(client, aid: str) -> str:
    return client.get(f"/api/assignments/{aid}").json()["assignment"]["state"]


# --------------------------------------------------------------------------- #
# Active hours — pure vectors
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("spec,hhmm,expected", [
    (None, (12, 0), True),
    ("09:00-17:00", (12, 0), True),
    ("09:00-17:00", (8, 59), False),
    ("09:00-17:00", (17, 0), False),
    ("22:00-06:00", (23, 30), True),   # wraps midnight
    ("22:00-06:00", (5, 59), True),
    ("22:00-06:00", (12, 0), False),
    ("garbage", (12, 0), True),        # malformed specs never lock a team out
])
def test_active_hours_vectors(spec, hhmm, expected):
    now = datetime(2026, 8, 10, *hhmm)
    assert in_active_hours(spec, now) is expected


# --------------------------------------------------------------------------- #
# Pause / resume from the card (K1)
# --------------------------------------------------------------------------- #
def test_pause_holds_and_resume_releases(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    team, root, s, a, agent, cfg = _fleet(client, make_org, mint_session)

    r = client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "paused"})
    assert r.status_code == 200 and r.json()["schedule"]["runState"] == "paused"

    hold = agent.get("/api/dp/assignment/current").json()
    assert "hold" in hold and hold["hold"]["reason"] == "paused"
    assert loop_tick(agent, cfg) == "idle"  # the runtime idles; never an error

    client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "running"})
    assert "hold" not in (agent.get("/api/dp/assignment/current").json() or {})
    # Work actually proceeds after resume.
    for _ in range(6):
        loop_tick(agent, cfg)
        if _state(client, a.id) == "delivering":
            break
    assert _state(client, a.id) == "delivering"


def test_schedule_validates_inputs(client, make_org):
    team = make_org()
    assert client.put(f"/api/teams/{team['id']}/schedule",
                      json={"runState": "warp"}).status_code == 400
    assert client.put(f"/api/teams/{team['id']}/schedule",
                      json={"priority": "urgent"}).status_code == 400
    assert client.put(f"/api/teams/{team['id']}/schedule",
                      json={"fallbackPolicy": ["yolo"]}).status_code == 400


# --------------------------------------------------------------------------- #
# The done-bar: window dies mid-run → hold at boundary → gate → scripted reset → resume
# --------------------------------------------------------------------------- #
def test_window_exhaustion_holds_and_auto_resumes(client, make_org, mint_session,
                                                  monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    team, root, s, a, agent, cfg = _fleet(client, make_org, mint_session)

    # Drive into executing — the session is mid-run when the window dies.
    for _ in range(3):
        loop_tick(agent, cfg)
        if _state(client, a.id) == "executing":
            break
    assert _state(client, a.id) == "executing"

    resets_at = "2027-01-01T00:00:00Z"
    r = agent.post("/api/dp/assignment/events", json={
        "assignmentId": a.id, "kind": "limit-signal", "signal": "mock-reading",
        "payload": {"windowKey": "mock_window", "utilizationPct": 100.0,
                    "source": "provider-event", "stateHint": "exhausted",
                    "resetsAt": resets_at},
    })
    assert r.status_code == 200

    # Turn boundary: the next poll holds and the capacity gate opens.
    hold = agent.get("/api/dp/assignment/current").json()
    assert "hold" in hold and hold["hold"]["reason"] == "window-exhausted"
    assert hold["hold"]["resetsAt"] == resets_at
    assert loop_tick(agent, cfg) == "idle"

    gates = client.get(f"/api/teams/{team['id']}/gates?state=open").json()["gates"]
    (gate,) = [g for g in gates if g["openedBy"] == "trigger:capacity"]
    # Scheduled waiting, legible: the payload carries pool, window, and the reset.
    assert gate["kind"] == "intervention"
    assert gate["payload"]["window"] == "mock_window"
    assert gate["payload"]["resetsAt"] == resets_at
    assert _state(client, a.id) == "gated"

    # The scripted reset passes (FakeClock) → the sweep resolves the gate, zero jitter.
    from canopy_server.capacity.ledger import CapacityLedger
    from canopy_server.capacity.service import CapacityService
    from canopy_server.deps import (
        get_db,
        get_engine,
        get_profile_store,
        get_provider_accounts,
        get_work_store,
    )
    from canopy_server.scheduler import Scheduler
    from test_capacity import FakeClock

    clock = FakeClock("2027-01-01T00:05:00Z")  # past the provider's reset
    # The whole sweep runs on ONE clock: at reset time, the gate timer fires AND the
    # window's effective state has decayed — the same coherence the real clock gives.
    ledger = CapacityLedger(get_db(), now=clock)
    service = CapacityService(get_provider_accounts(), ledger, get_profile_store(),
                              enabled=lambda: True)
    sweeper = Scheduler(
        get_db(), now=clock, capacity_service=service,
        capacity_ledger=ledger, work_store=get_work_store(),
        gates=get_engine().gates, enabled=lambda: True, resume_jitter_s=0,
    )
    assert sweeper.sweep() == 1
    assert _state(client, a.id) == "executing"  # the conversation continues where it stopped

    # Reality's second half: the first successful call after the reset flips the window
    # back to ok (the session-ok signal) — record it so live admission agrees too.
    from canopy_server.capacity.adapters import WindowReading
    from canopy_server.deps import get_capacity_ledger, get_provider_accounts

    acct = get_provider_accounts().find("mock", "mock")
    get_capacity_ledger().record_reading(acct.id, WindowReading(
        window_key="mock_window", source="provider-event", state_hint="ok",
        detail="post-reset-ok"))

    # And the fleet finishes normally after the window came back.
    for _ in range(6):
        loop_tick(agent, cfg)
        if _state(client, a.id) == "delivering":
            break
    assert _state(client, a.id) == "delivering"


# --------------------------------------------------------------------------- #
# Admission table (04 §2) — state × window → admit/hold + reason
# --------------------------------------------------------------------------- #
def test_admission_table(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_scheduler, get_work_store

    team, root, s, a, agent, cfg = _fleet(client, make_org, mint_session)
    sched = get_scheduler()
    work = get_work_store()
    assignment = work.get_assignment(a.id)  # state: briefed (pre-session)

    # drain blocks pre-session work but not a running session
    client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "drain"})
    assert sched.check(team["id"], root["id"], assignment).reason == "drain"
    executing = assignment.model_copy(update={"state": "executing"})
    assert sched.check(team["id"], root["id"], executing).admit is True

    # paused blocks everything
    client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "paused"})
    assert sched.check(team["id"], root["id"], executing).reason == "paused"

    # session cap gates NEW sessions only
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"runState": "running", "maxConcurrentSessions": 0})
    assert sched.check(team["id"], root["id"], assignment).reason == "session-cap"
    assert sched.check(team["id"], root["id"], executing).admit is True


# --------------------------------------------------------------------------- #
# The degrade-model rung (04 §5 rung 2)
# --------------------------------------------------------------------------- #
def test_degrade_model_admits_with_override(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_capacity_ledger, get_capacity_service, get_scheduler

    team, root, s, a, agent, cfg = _fleet(client, make_org, mint_session)
    account = get_capacity_service().account_for_session(team["id"], root["id"])
    from canopy_server.capacity.adapters import WindowReading

    # Only the model-scoped window is shut.
    get_capacity_ledger().record_reading(account.id, WindowReading(
        window_key="seven_day_opus", source="provider-event", utilization_pct=100.0,
        resets_at="2027-01-01T00:00:00Z", state_hint="exhausted"))
    with get_capacity_ledger().db.transaction() as conn:
        conn.execute("UPDATE capacity_window SET model_scope='opus' WHERE key=?",
                     ("seven_day_opus",))

    sched = get_scheduler()
    work_assignment = None  # spawn decision, no live assignment needed

    # Without a fallback tier: the scoped window binds → hold.
    client.put(f"/api/teams/{team['id']}/schedule", json={"fallbackPolicy": ["hold-resume"]})
    held = sched.check(team["id"], root["id"], work_assignment)
    assert held.admit is False and held.payload["window"] == "seven_day_opus"

    # With degrade-model + a tier cap: admit, next chunk runs on the fallback tier.
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"fallbackPolicy": ["hold-resume", "degrade-model"],
                     "modelTierCap": "sonnet"})
    degraded = sched.check(team["id"], root["id"], work_assignment)
    assert degraded.admit is True and degraded.model_override == "sonnet"
    assert degraded.reason == "degrade-model"
