"""The cli-claude adapter + fake-CLI shim + MCP server, integrated (cli-runtime.md §9).

The adapter runs in-process; the fake CLI runs as a REAL subprocess and calls the MCP server
over REAL HTTP (a uvicorn thread on an ephemeral port) — the same wire a logged-in `claude`
would use. Zero external calls; both OSes (the Windows process-group kill path is exactly what
this suite exercises on windows-latest).
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))

from canopy_agent import cli_runtime  # noqa: E402
from canopy_agent.runtime import AgentConfig  # noqa: E402

FAKE_CLI = Path(__file__).resolve().parent / "fake_claude.py"


@pytest.fixture()
def live_server(client):
    """A real HTTP server over the same app + test DB, for the fake-CLI subprocess."""
    import uvicorn

    from canopy_server.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn thread never started")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _seed_charter(org: dict, actuation_id: str, node_id: str) -> None:
    """Store a real compiled charter (incl. E3 toolGrants) the way the actuator would."""
    from canopy_server.catalog import get_catalog
    from canopy_server.charter import compile_charter
    from canopy_server.deps import get_db, get_store, now_iso

    top = get_store().read(org["id"])
    charter = compile_charter(top, [], node_id, catalog=get_catalog(),
                              actuation_id=actuation_id)
    ts = now_iso()
    with get_db().transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO actuation (id, org_id, state, created_at, updated_at) "
            "VALUES (?,?,?,?,?)",
            (actuation_id, org["id"], "live", ts, ts),
        )
        conn.execute(
            "INSERT OR IGNORE INTO actuation_node (actuation_id, node_id, org_path, sub_state, "
            "charter, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (actuation_id, node_id, "[]", "running",
             json.dumps(charter.model_dump() if charter else {}), ts, ts),
        )


def _agent(client_headers_token: str):
    from canopy_server.main import app

    return TestClient(app, headers={"Authorization": f"Bearer {client_headers_token}"})


def _cfg(live_url: str, s: dict, node_id: str) -> AgentConfig:
    return AgentConfig(cp_url=live_url, run_token=s["token"], node_id=node_id,
                       actuation_id=s["actuationId"], a2a_host="127.0.0.1", a2a_port=0)


def _wait_session_done(aid: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        session = cli_runtime._SESSIONS.get(aid)
        if session is not None and not session.alive:
            return
        time.sleep(0.1)
    raise AssertionError(f"session for {aid} never finished")


def _write_script(tmp_path: Path, monkeypatch, script: dict) -> None:
    path = tmp_path / "fake_script.json"
    path.write_text(json.dumps(script), encoding="utf-8")
    monkeypatch.setenv("FAKE_CLAUDE_SCRIPT", str(path))
    monkeypatch.setenv("CANOPY_CLI_CMD", json.dumps([sys.executable, str(FAKE_CLI)]))


def _node(org: dict, role_key: str) -> dict:
    return next(a for a in org["agents"] if a["role"]["key"] == role_key)


def test_cli_adapter_drives_assignment_via_fake_cli(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """INTAKE → CONFIG → RUN → OBSERVE → DISCHARGE on the fake CLI: the session declares its
    plan and finishes THROUGH the MCP server; the adapter reports settled Steps."""
    from canopy_server.deps import get_engine, get_ledger

    monkeypatch.chdir(tmp_path)  # the adapter materializes assignments/<id>/ under cwd
    org = make_org(seed={"kind": "root", "roleKey": "backend-engineer"})
    node = _node(org, "backend-engineer")
    s = mint_session(org["id"], node_id=node["id"])
    _seed_charter(org, s["actuationId"], node["id"])
    a = get_engine().submit_intent(org["id"], s["actuationId"], "implement the CSV export",
                                   target_node=node["id"], allowance_override=50_000).assignment

    _write_script(tmp_path, monkeypatch, {
        "sessionId": "sess-be-1",
        "turns": [
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "implement"}]}}],
             "usage": [150, 30]},
            {"tools": [{"name": "produce_artifact",
                        "arguments": {"name": "pr", "type": "code-patch",
                                      "content": "the diff"}},
                       {"name": "finish",
                        "arguments": {"refs": [], "summary": "done via fake CLI"}}],
             "usage": [400, 80]},
        ],
    })

    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    assert cli_runtime.cli_tick(agent, cfg) == "engaged"  # briefed -> intake-complete
    assert cli_runtime.cli_tick(agent, cfg) == "engaged"  # planning -> session starts
    _wait_session_done(a.id)

    detail = client.get(f"/api/assignments/{a.id}").json()
    assert detail["assignment"]["state"] == "delivering"  # the session discharged via MCP
    assert detail["assignment"]["sessionRef"] == "sess-be-1"  # the resume handle
    # Session config was compiled, never authored: grants -> permissions, one MCP server.
    workdir = tmp_path / "assignments" / a.id / "work"
    perms = json.loads((workdir / ".claude" / "settings.json").read_text())["permissions"]
    assert "Bash(uv run pytest tests/unit*)" in perms["allow"]  # test.unit.run
    assert "Bash(uv run pytest tests*)" not in perms["allow"]  # NOT test.run (QA's grant)
    assert "WebFetch" in perms["deny"]
    mcp_conf = json.loads((workdir / ".mcp.json").read_text())
    assert list(mcp_conf["mcpServers"]) == ["canopy"]
    # Every assistant turn landed as a SETTLED step: work_step + SpendEvent + meter spend.
    steps = detail["steps"]
    session_steps = [st for st in steps if st["sessionSpanId"] == "sess-be-1"]
    assert len(session_steps) == 2
    meter = get_ledger().get_meter(a.meterId)
    assert meter.spent == 150 + 30 + 400 + 80  # CLI-reported usage, ledger-settled (E-D2)


def test_cli_adapter_budget_boundary_halt(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """One turn overshoots the allowance (debt E-D1): the settled step trips the hard-stop
    trigger, the adapter kills the process tree at the boundary, the assignment gates."""
    from canopy_server.deps import get_engine

    monkeypatch.chdir(tmp_path)
    org = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="Tight")
    node = _node(org, "backend-engineer")
    s = mint_session(org["id"], node_id=node["id"])
    _seed_charter(org, s["actuationId"], node["id"])
    a = get_engine().submit_intent(org["id"], s["actuationId"], "tiny budget",
                                   target_node=node["id"], allowance_override=100).assignment

    _write_script(tmp_path, monkeypatch, {
        "sessionId": "sess-halt",
        "turns": [
            # Declares its plan (-> executing), then the turn's usage overshoots.
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "work"}]}}],
             "usage": [200, 50]},
            {"tools": [], "usage": [999, 999]},  # must never be reported
        ],
    })
    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    cli_runtime.cli_tick(agent, cfg)  # intake
    cli_runtime.cli_tick(agent, cfg)  # session
    _wait_session_done(a.id)

    detail = client.get(f"/api/assignments/{a.id}").json()
    assert detail["assignment"]["state"] == "gated"
    gate = next(g for g in detail["gates"]
                if g["state"] == "open" and g["openedBy"] == "trigger:hard-stop")
    assert gate["kind"] == "intervention"
    session_steps = [st for st in detail["steps"] if st["sessionSpanId"] == "sess-halt"]
    assert len(session_steps) == 1  # the boundary held: turn 2 never landed
    assert detail["meter"]["spent"] == 250  # the overshoot is honest (E-D1), and visible


def test_two_node_delegate_demo_on_fake_cli(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """The mvp E3 demo: a 2-node org runs delegate → work → finish → accept on the fake CLI,
    with the lead's staged fan-out approved by the operator and the resume via --resume."""
    from canopy_server.deps import get_engine, get_work_store

    monkeypatch.chdir(tmp_path)
    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead, be = _node(org, "engineering-lead"), _node(org, "backend-engineer")
    s_lead = mint_session(org["id"], node_id=lead["id"])
    s_be = mint_session(org["id"], node_id=be["id"], actuation_id=s_lead["actuationId"])
    _seed_charter(org, s_lead["actuationId"], lead["id"])
    _seed_charter(org, s_lead["actuationId"], be["id"])
    eng = get_engine()
    root = eng.submit_intent(org["id"], s_lead["actuationId"], "ship CSV; tests must pass",
                             target_node=lead["id"]).assignment

    # Phase 1 — the lead's session decomposes and fans out (staged), then ends its turn.
    _write_script(tmp_path, monkeypatch, {
        "sessionId": "sess-lead",
        "turns": [
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "decompose"},
                                                 {"title": "review"}]}},
                       {"name": "delegate",
                        "arguments": {"reportNodeId": be["id"],
                                      "brief": "implement CSV export",
                                      "contractType": "PullRequest"}},
                       {"name": "finish_turn", "arguments": {}}],
             "usage": [500, 120]},
        ],
        "resumeTurns": [
            {"tools": [{"name": "reports_status", "arguments": {}}], "usage": [80, 10]},
        ],
    })
    lead_agent = _agent(s_lead["token"])
    lead_cfg = _cfg(live_server, s_lead, lead["id"])
    cli_runtime.cli_tick(lead_agent, lead_cfg)  # intake
    cli_runtime.cli_tick(lead_agent, lead_cfg)  # session (plan + staged fan-out + finish_turn)
    _wait_session_done(root.id)
    assert client.get(f"/api/assignments/{root.id}").json()["assignment"]["state"] == "gated"

    # The operator approves the real batch.
    gates = client.get(f"/api/organizations/{org['id']}/gates?state=open&owner=operator").json()
    gate = next(g for g in gates["gates"] if g["kind"] == "approval")
    child_id = gate["payload"]["batch"][0]["assignmentId"]
    client.post(f"/api/gates/{gate['id']}/resolve", json={"action": "approve"})

    # Phase 2 — the engineer's session does the work.
    _write_script(tmp_path, monkeypatch, {
        "sessionId": "sess-be",
        "turns": [
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "implement"}]}},
                       {"name": "produce_artifact",
                        "arguments": {"name": "pr", "type": "code-patch",
                                      "content": "diff"}},
                       {"name": "finish", "arguments": {"summary": "PR v1"}}],
             "usage": [900, 200]},
        ],
    })
    be_agent = _agent(s_be["token"])
    be_cfg = _cfg(live_server, s_be, be["id"])
    cli_runtime.cli_tick(be_agent, be_cfg)  # intake
    cli_runtime.cli_tick(be_agent, be_cfg)  # session
    _wait_session_done(child_id)
    assert client.get(f"/api/assignments/{child_id}").json()["assignment"]["state"] \
        == "delivering"

    # Phase 3 — the delivery woke the lead; the adapter RESUMES the suspended conversation.
    assert client.get(f"/api/assignments/{root.id}").json()["assignment"]["state"] \
        == "executing"
    _write_script(tmp_path, monkeypatch, {  # back to the LEAD's script for the resume
        "sessionId": "sess-lead",
        "turns": [],
        "resumeTurns": [
            {"tools": [{"name": "reports_status", "arguments": {}}], "usage": [80, 10]},
        ],
    })
    cli_runtime._SESSIONS.pop(root.id, None)  # prior session object is spent
    cli_runtime.cli_tick(lead_agent, lead_cfg)
    _wait_session_done(root.id)
    # The resume script only checked reports_status; the review verdict is scripted here:
    eng.accept(child_id, note="contract met")
    assert get_work_store().get_assignment(child_id).state == "closed"

    # The fake CLI was invoked with --resume for the lead's second session (same session id
    # stored, resumeTurns executed) — reports_status landed a ToolEvent for the lead.
    events = [e["tool"] for e in
              get_work_store().list_tool_events(s_lead["actuationId"], lead["id"])]
    assert "reports_status" in events


def test_read_only_poll_loop_trips_stall_trigger(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """Regression: a session that only calls read-only status tools (get_assignment,
    reports_status, fetch_artifact) settles NO-DELTA steps, so the engine's no-delta stall
    trigger gates the spin. Previously any tool call counted as "tool-effect", so an agent
    politely polling forever was invisible to stall detection and burned a session per
    resume."""
    from canopy_server.deps import get_engine

    monkeypatch.chdir(tmp_path)
    org = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="Spin")
    node = _node(org, "backend-engineer")
    s = mint_session(org["id"], node_id=node["id"])
    _seed_charter(org, s["actuationId"], node["id"])
    a = get_engine().submit_intent(org["id"], s["actuationId"], "spin regression",
                                   target_node=node["id"], allowance_override=50_000).assignment

    poll = {"tools": [{"name": "get_assignment", "arguments": {}}], "usage": [50, 10]}
    _write_script(tmp_path, monkeypatch, {
        "sessionId": "sess-spin",
        "turns": [
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "work"}]}}],
             "usage": [100, 20]},
            poll, poll, poll, poll, poll,  # 5 = the stall_none_steps default
        ],
    })
    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    cli_runtime.cli_tick(agent, cfg)  # intake
    cli_runtime.cli_tick(agent, cfg)  # session
    _wait_session_done(a.id)

    detail = client.get(f"/api/assignments/{a.id}").json()
    no_delta = [st for st in detail["steps"] if st["deltaKind"] == "none"]
    assert len(no_delta) >= 5  # read-only polls are not progress

    # F14 changed the trigger's tempo, not its verdict: while the session streams, the
    # adapter's liveness reports defer the no-delta gate (a thinking session is not a spin).
    assert get_engine().sweep_triggers() == []  # fresh liveness → deferred, not gated
    # Once the activity is stale past the grace window the spin gates as before — collapse
    # the window rather than forging timestamps (which would scramble step ordering).
    from canopy_server.engine.engine import ExecutionEngine

    monkeypatch.setattr(ExecutionEngine, "NO_DELTA_ACTIVITY_GRACE_SECONDS", 0)
    gates = get_engine().sweep_triggers()
    gate = next(g for g in gates if g.reason.startswith("stall:no-delta"))
    assert gate.assignmentId == a.id
    assert client.get(f"/api/assignments/{a.id}").json()["assignment"]["state"] == "gated"
