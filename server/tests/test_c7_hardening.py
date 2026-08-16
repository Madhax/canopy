"""C7 hardening (design/organizations/07 §1, row C7) — the E6-style audit for the capacity
layer, plus the fold-in items the series left for its last milestone:

- a control-plane restart mid-hold resumes correctly (04 §7: gates + schedules are SQLite
  truth; the boot pass of the trigger loop re-evaluates every open capacity gate, so a
  reset that passed during downtime resolves at once and the conversation continues on
  its stored ``--resume`` handle);
- redelivered boundary polls are idempotent (one gate row however often the runtime asks);
- every hold-resume leaves its ``hold-resumed`` feed row, operator/clock holds included;
- the two sweeps in the trigger loop are isolated from each other's failures;
- reading retention compacts without losing any window's provenance (02 §9.3);
- cadence occurrences consult the governor before they submit (04 §9.4).
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

_AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))

from canopy_agent.runtime import AgentConfig, loop_tick  # noqa: E402

from test_capacity import FakeClock  # noqa: E402


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _root_of(team: dict) -> dict:
    return next(a for a in team["agents"] if a["managerId"] is None)


def _seed_live_actuation(actuation_id: str, team_id: str) -> None:
    from canopy_server.deps import get_db, now_iso

    ts = now_iso()
    with get_db().transaction() as conn:
        conn.execute(
            "INSERT INTO actuation (id, team_id, state, created_at, updated_at) VALUES (?,?,?,?,?)",
            (actuation_id, team_id, "live", ts, ts),
        )


def _mint(team: dict, root: dict) -> dict:
    """The conftest ``mint_session`` factory, inlined for tests that own their TestClient."""
    from canopy_server.deps import get_ledger, get_profile_store, get_runtokens
    from canopy_server.ids import new_actuation_id
    from canopy_server.profiles import ProfileParams

    profiles = get_profile_store()
    profile = profiles.create_profile(
        team["id"], name="p", provider="mock", model="mock-1",
        api_key_secret_id=None, params=ProfileParams(maxOutputTokens=4096),
    )
    profiles.set_binding(team["id"], root["id"], profile.id)
    actuation_id = new_actuation_id()
    meter = get_ledger().open_meter(actuation_id, root["id"], 5000)
    token, _ = get_runtokens().issue(actuation_id, root["id"], team["id"],
                                     default_meter_id=meter.id)
    return {"token": token, "actuationId": actuation_id, "nodeId": root["id"]}


def _restart_process() -> None:
    """Drop every cached singleton so the next app builds fresh objects over the same
    on-disk state — the honest simulation of a new process (test_hardening's idiom)."""
    import canopy_server.config as config
    import canopy_server.deps as deps

    for mod in (deps, config):
        for name in dir(mod):
            fn = getattr(mod, name)
            if hasattr(fn, "cache_clear"):
                fn.cache_clear()


def _state(client, aid: str) -> str:
    return client.get(f"/api/assignments/{aid}").json()["assignment"]["state"]


def _capacity_gates(client, team_id: str, state: str = "open") -> list[dict]:
    gates = client.get(f"/api/teams/{team_id}/gates?state={state}").json()["gates"]
    return [g for g in gates if g["openedBy"] == "trigger:capacity"]


def _feed(kind: str) -> list[dict]:
    from canopy_server.deps import get_capacity_ledger, get_provider_accounts

    acct = get_provider_accounts().find("mock", "mock")
    return [e for e in get_capacity_ledger().events(acct.id) if e["kind"] == kind]


# --------------------------------------------------------------------------- #
# The audit: control-plane restart mid-hold
# --------------------------------------------------------------------------- #
def test_control_plane_restart_mid_hold_resumes(tmp_path, monkeypatch):
    """Session held behind a capacity gate → the control plane dies → the provider's
    reset passes during the downtime → the new process's boot sweep resolves the gate,
    the assignment is executing again on its stored resume handle, and the redelivered
    boundary polls before and after the crash left exactly one gate row."""
    monkeypatch.setenv("CANOPY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    import canopy_server.config as config

    # Zero resume jitter for the test's real clock (04 §7's ±120 s is production etiquette).
    monkeypatch.setattr(config, "get_scheduler_resume_jitter_s", lambda: 0)
    _restart_process()
    from canopy_server.main import app, sweep_once

    with TestClient(app) as c1:
        team = c1.post("/api/teams", json={
            "name": "Held", "organizationType": "product-engineering",
            "seed": {"kind": "root", "roleKey": "engineering-lead"},
        }).json()
        root = _root_of(team)
        s = _mint(team, root)
        _seed_live_actuation(s["actuationId"], team["id"])
        a = c1.post(f"/api/teams/{team['id']}/intents",
                    json={"text": "write the report", "targetNodeId": root["id"]},
                    ).json()["assignment"]
        agent = TestClient(app, headers=_h(s["token"]))
        cfg = AgentConfig(cp_url="http://cp", run_token=s["token"], node_id=root["id"],
                          actuation_id=s["actuationId"], a2a_host="127.0.0.1", a2a_port=0)
        for _ in range(3):
            loop_tick(agent, cfg)
            if _state(c1, a["id"]) == "executing":
                break
        assert _state(c1, a["id"]) == "executing"
        # The adapter stored its resume handle the moment the session began.
        agent.post("/api/dp/assignment/events", json={
            "assignmentId": a["id"], "kind": "session-ref", "sessionRef": "sess-held-1"})

        # The window dies mid-run; the provider says it resets shortly.
        resets_at = (datetime.now(UTC) + timedelta(seconds=1.5)).isoformat() \
            .replace("+00:00", "Z")
        agent.post("/api/dp/assignment/events", json={
            "assignmentId": a["id"], "kind": "limit-signal", "signal": "mock-reading",
            "payload": {"windowKey": "mock_window", "utilizationPct": 100.0,
                        "source": "provider-event", "stateHint": "exhausted",
                        "resetsAt": resets_at},
        })
        # Turn boundary — and the runtime keeps polling while held (redelivery): one gate.
        for _ in range(3):
            hold = agent.get("/api/dp/assignment/current").json()
            assert hold["hold"]["reason"] == "window-exhausted"
        assert _state(c1, a["id"]) == "gated"
        assert len(_capacity_gates(c1, team["id"])) == 1
        assert _feed("hold-resumed") == []

    # Downtime: the provider's reset passes while nobody is home.
    time.sleep(1.8)
    _restart_process()
    monkeypatch.setattr(config, "get_scheduler_resume_jitter_s", lambda: 0)

    with TestClient(app) as c2:
        # The boot pass of the trigger loop is exactly this call; running it explicitly
        # keeps the test deterministic (it is idempotent with the loop's own first pass).
        counts = sweep_once()
        assert counts["capacity"] >= 0  # the capacity sweep RAN on the new process
        assert _state(c2, a["id"]) == "executing"  # the conversation continues
        assert _capacity_gates(c2, team["id"]) == []
        (gate,) = _capacity_gates(c2, team["id"], state="resolved")
        assert gate["resolvedBy"] == "system"
        assert gate["resolution"]["by"] == "trigger:capacity"
        detail = c2.get(f"/api/assignments/{a['id']}").json()["assignment"]
        assert detail["sessionRef"] == "sess-held-1"  # the --resume handle survived
        # The feed says so, once.
        resumed = _feed("hold-resumed")
        assert len(resumed) == 1 and resumed[0]["payload"]["assignmentId"] == a["id"]
        assert resumed[0]["payload"]["reason"] == "exhausted"

        # Admission on the new process agrees: no hold on the next poll, and a redelivered
        # boundary poll after the resume opens nothing new.
        agent2 = TestClient(app, headers=_h(s["token"]))
        cur = agent2.get("/api/dp/assignment/current").json()
        assert "hold" not in cur and cur["assignment"]["sessionRef"] == "sess-held-1"
        assert _capacity_gates(c2, team["id"]) == []


# --------------------------------------------------------------------------- #
# Feed symmetry: operator holds resume with a row too
# --------------------------------------------------------------------------- #
def test_operator_hold_resume_leaves_feed_row(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_engine, get_scheduler
    from canopy_server.main import app

    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(team)
    s = mint_session(team["id"], node_id=root["id"])
    a = get_engine().submit_intent(team["id"], s["actuationId"], "write the report",
                                   target_node=root["id"]).assignment
    agent = TestClient(app, headers=_h(s["token"]))
    cfg = AgentConfig(cp_url="http://cp", run_token=s["token"], node_id=root["id"],
                      actuation_id=s["actuationId"], a2a_host="127.0.0.1", a2a_port=0)
    for _ in range(3):
        loop_tick(agent, cfg)
        if _state(client, a.id) == "executing":
            break
    assert _state(client, a.id) == "executing"

    client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "paused"})
    assert agent.get("/api/dp/assignment/current").json()["hold"]["reason"] == "paused"
    assert _state(client, a.id) == "gated"

    client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "running"})
    assert get_scheduler().sweep() == 1
    assert _state(client, a.id) == "executing"
    (row,) = _feed("hold-resumed")
    assert row["team_id"] == team["id"] and row["payload"]["reason"] == "paused"


# --------------------------------------------------------------------------- #
# The two sweeps are isolated
# --------------------------------------------------------------------------- #
def test_sweep_once_isolates_stall_and_capacity_sweeps(client, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.engine.engine import ExecutionEngine
    from canopy_server.main import sweep_once

    def boom(_self):
        raise RuntimeError("stall sweep exploded")

    monkeypatch.setattr(ExecutionEngine, "sweep_triggers", boom)
    counts = sweep_once()
    assert counts["triggers"] == -1  # it raised, and was contained
    assert counts["capacity"] == 0  # the capacity sweep still ran (nothing to resolve)


# --------------------------------------------------------------------------- #
# Reading retention (02 §9.3)
# --------------------------------------------------------------------------- #
def test_reading_retention_keeps_each_windows_newest(client, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.capacity.adapters import WindowReading
    from canopy_server.capacity.ledger import CapacityLedger
    from canopy_server.deps import get_db, get_provider_accounts

    acct = get_provider_accounts().ensure_mock_account()
    today = datetime(2026, 8, 15, 12, tzinfo=UTC)
    clock = FakeClock("2026-08-15T12:00:00Z")
    ledger = CapacityLedger(get_db(), now=clock)

    def at(days_ago: float, key: str, pct: float) -> None:
        clock.now = today - timedelta(days=days_ago)
        ledger.record_reading(acct.id, WindowReading(
            window_key=key, source="provider-read", utilization_pct=pct))

    at(40, "five_hour", 10.0)
    at(35, "five_hour", 20.0)
    at(1, "five_hour", 30.0)
    at(60, "seven_day", 5.0)  # a window whose ONLY reading is ancient
    clock.now = today
    ledger.record_event(acct.id, "old-event")
    clock.now = today - timedelta(days=136)
    ledger.record_event(acct.id, "ancient-event")
    clock.now = today

    def rows(table: str) -> int:
        with get_db().connect() as conn:
            return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    assert rows("capacity_reading") == 4 and rows("capacity_event") == 2

    # Retention 0 = keep forever (the documented escape hatch).
    assert ledger.prune(reading_retention_days=0, event_retention_days=0) == \
        {"readings": 0, "events": 0}
    assert rows("capacity_reading") == 4

    removed = ledger.prune(reading_retention_days=30, event_retention_days=90)
    assert removed == {"readings": 2, "events": 1}
    # five_hour lost its two ancient readings; seven_day kept its only one — the window
    # still knows where its state came from.
    assert ledger.window(acct.id, "seven_day")["utilization_pct"] == 5.0
    with get_db().connect() as conn:
        kept = conn.execute(
            "SELECT w.key AS key, r.utilization_pct AS pct FROM capacity_reading r"
            " JOIN capacity_window w ON w.id = r.window_id ORDER BY w.key, r.observed_at"
        ).fetchall()
    assert [(k["key"], k["pct"]) for k in kept] == [("five_hour", 30.0), ("seven_day", 5.0)]
    assert [e["kind"] for e in ledger.events(acct.id)] == ["old-event"]
    # Idempotent.
    assert ledger.prune(reading_retention_days=30, event_retention_days=90) == \
        {"readings": 0, "events": 0}


# --------------------------------------------------------------------------- #
# Cadences consult the governor (04 §9.4)
# --------------------------------------------------------------------------- #
def _standing(client, team: dict, root: dict) -> dict:
    r = client.post(f"/api/teams/{team['id']}/cadences", json={
        "name": "nightly", "cron": "0 3 * * *",
        "intentText": "Run the nightly maintenance pass", "nodeId": root["id"],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _skips(team_id: str) -> list[dict]:
    from canopy_server.deps import get_activity

    return [row["payload"] for row in get_activity().list(team_id, after_seq=0, limit=500)
            if row["kind"] == "cadence.skipped"]


def _spend_this_week(team_id: str, usd: float, tag: str) -> None:
    from canopy_server.deps import get_db, now_iso

    with get_db().transaction() as conn:
        conn.execute(
            "INSERT INTO ledger_spend_event (id, step_id, team_id, actuation_id, node_id,"
            " task_id, provider, model, input_tokens, output_tokens, cache_read_tokens,"
            " cache_creation_tokens, est_cost_micros, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"sp_{tag}", f"st_{tag}", team_id, "act_x", "a_x", None, "mock", "mock-1",
             100, 100, 0, 0, int(usd * 1e6), now_iso()),
        )


def test_cadence_consults_the_governor(client, make_org, mint_session, monkeypatch):
    """The standing-intent boundary: budget, operator, provider — each a skip-with-note
    that consumes the occurrence; a rung that admits lets it fire; spawn-time waits
    (active hours) do not skip."""
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.capacity.adapters import WindowReading
    from canopy_server.deps import (
        get_cadence_scheduler,
        get_capacity_ledger,
        get_provider_accounts,
        get_work_store,
    )

    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(team)
    org = client.post("/api/orgs", json={"key": "nightly", "name": "Nightly"}).json()
    moved = client.post(f"/api/teams/{team['id']}/move", json={"organizationId": org["id"]})
    assert moved.status_code == 200, moved.text  # before actuation: live teams don't move
    s = mint_session(team["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], team["id"])
    _standing(client, team, root)
    cadences = get_cadence_scheduler()
    day = 0

    def tick() -> list:
        nonlocal day
        day += 1
        return cadences.run_once(datetime.now(UTC) + timedelta(days=day))

    # 1. Budget: the org's weekly ceiling is spent → skipped, reason budget, with the facts.
    client.put(f"/api/orgs/{org['id']}/budget", json={"weeklyCostCeilingUsd": 5.0})
    _spend_this_week(team["id"], 6.0, "ceiling")
    assert tick() == []
    (skip,) = _skips(team["id"])
    assert skip["reason"] == "budget" and skip["admission"] == "org-budget"
    assert skip["weekSpendUsd"] == 6.0 and skip["ceilingUsd"] == 5.0
    assert get_work_store().list_intents(team["id"]) == []
    client.put(f"/api/orgs/{org['id']}/budget", json={"weeklyCostCeilingUsd": None})

    # 2. Operator: a paused team banks nothing.
    client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "paused"})
    assert tick() == []
    assert _skips(team["id"])[-1]["reason"] == "paused"
    client.put(f"/api/teams/{team['id']}/schedule", json={"runState": "running"})

    # 3. Provider: the binding window is exhausted, hold-resume only → skipped, with the
    #    reset in the note; the occurrence stays consumed (coalesces, like a misfire).
    acct = get_provider_accounts().ensure_mock_account()
    get_capacity_ledger().record_reading(acct.id, WindowReading(
        window_key="mock_window", source="provider-event", utilization_pct=100.0,
        resets_at="2027-01-01T00:00:00Z", state_hint="exhausted"))
    assert tick() == []
    skip = _skips(team["id"])[-1]
    assert skip["reason"] == "capacity" and skip["admission"] == "window-exhausted"
    assert skip["resetsAt"] == "2027-01-01T00:00:00Z"
    assert get_work_store().list_intents(team["id"]) == []

    # 3b. A rung that admits lets it fire: extra-usage opted in with cap headroom.
    client.put(f"/api/capacity/accounts/{acct.id}", json={"extraUsageCapUsd": 20.0})
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"fallbackPolicy": ["extra-usage", "hold-resume"]})
    fired = tick()
    assert len(fired) == 1 and fired[0].createdBy == "cadence"

    # 4. Active hours are a queue, not a door: outside them the cadence still fires and
    #    the intent simply waits at admission.
    from canopy_server.deps import get_engine

    get_engine().cancel_assignment(fired[0].rootAssignmentId)
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"activeHours": "00:00-00:01", "fallbackPolicy": ["extra-usage"]})
    assert len(tick()) == 1
