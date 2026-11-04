"""The cli-claude adapter + fake-CLI shim + MCP server, integrated (cli-runtime.md §9).

The adapter runs in-process; the fake CLI runs as a REAL subprocess and calls the MCP server
over REAL HTTP (a uvicorn thread on an ephemeral port) — the same wire a logged-in `claude`
would use. Zero external calls; both OSes (the Windows process-group kill path is exactly what
this suite exercises on windows-latest).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

_AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))

from canopy_agent import cli_runtime  # noqa: E402
from canopy_agent.runtime import AgentConfig  # noqa: E402

FAKE_CLI = Path(__file__).resolve().parent / "fake_claude.py"

# The `live_server` fixture (real uvicorn over the test DB) lives in conftest.py — shared
# with the marked live smoke (test_live_smoke.py), which drives a real `claude` down the
# same wire.


def _seed_charter(team: dict, actuation_id: str, node_id: str) -> None:
    """Store a real compiled charter (incl. E3 toolGrants) the way the actuator would."""
    from canopy_server.catalog import get_catalog
    from canopy_server.charter import compile_charter
    from canopy_server.deps import get_db, get_store, now_iso

    top = get_store().read(team["id"])
    charter = compile_charter(top, [], node_id, catalog=get_catalog(),
                              actuation_id=actuation_id)
    ts = now_iso()
    with get_db().transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO actuation (id, team_id, state, created_at, updated_at) "
            "VALUES (?,?,?,?,?)",
            (actuation_id, team["id"], "live", ts, ts),
        )
        conn.execute(
            "INSERT OR IGNORE INTO actuation_node (actuation_id, node_id, team_path, sub_state, "
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


def _node(team: dict, role_key: str) -> dict:
    return next(a for a in team["agents"] if a["role"]["key"] == role_key)


def test_cli_adapter_drives_assignment_via_fake_cli(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """INTAKE → CONFIG → RUN → OBSERVE → DISCHARGE on the fake CLI: the session declares its
    plan and finishes THROUGH the MCP server; the adapter reports settled Steps."""
    from canopy_server.deps import get_engine, get_ledger

    monkeypatch.chdir(tmp_path)  # the adapter materializes assignments/<id>/ under cwd
    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"})
    node = _node(team, "backend-engineer")
    s = mint_session(team["id"], node_id=node["id"])
    _seed_charter(team, s["actuationId"], node["id"])
    a = get_engine().submit_intent(team["id"], s["actuationId"], "implement the CSV export",
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
    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="Tight")
    node = _node(team, "backend-engineer")
    s = mint_session(team["id"], node_id=node["id"])
    _seed_charter(team, s["actuationId"], node["id"])
    a = get_engine().submit_intent(team["id"], s["actuationId"], "tiny budget",
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
    """The mvp E3 demo: a 2-node team runs delegate → work → finish → accept on the fake CLI,
    with the lead's staged fan-out approved by the operator and the resume via --resume."""
    from canopy_server.deps import get_engine, get_work_store

    monkeypatch.chdir(tmp_path)
    team = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead, be = _node(team, "engineering-lead"), _node(team, "backend-engineer")
    s_lead = mint_session(team["id"], node_id=lead["id"])
    s_be = mint_session(team["id"], node_id=be["id"], actuation_id=s_lead["actuationId"])
    _seed_charter(team, s_lead["actuationId"], lead["id"])
    _seed_charter(team, s_lead["actuationId"], be["id"])
    eng = get_engine()
    root = eng.submit_intent(team["id"], s_lead["actuationId"], "ship CSV; tests must pass",
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
    gates = client.get(f"/api/teams/{team['id']}/gates?state=open&owner=operator").json()
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


def test_work_root_is_stable_and_transcript_recorded(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """F13 + F16: with CANOPY_WORK_ROOT set, the assignment tree materializes under the
    actuation-independent home (NOT the sandbox cwd — the CLI's conversation key must not
    embed the actuation id), the transcript pointer lands on the assignment, and the
    transcript is archived into the assignment's own home at session exit."""
    from canopy_server.deps import get_engine

    sandbox_cwd = tmp_path / "sandboxes" / "act-ephemeral" / "n1" / "workspace"
    sandbox_cwd.mkdir(parents=True)
    stable = tmp_path / "work" / "org1" / "n1"
    monkeypatch.chdir(sandbox_cwd)
    monkeypatch.setenv("CANOPY_WORK_ROOT", str(stable))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))

    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="Stable")
    node = _node(team, "backend-engineer")
    s = mint_session(team["id"], node_id=node["id"])
    _seed_charter(team, s["actuationId"], node["id"])
    a = get_engine().submit_intent(team["id"], s["actuationId"], "stable home",
                                   target_node=node["id"], allowance_override=50_000).assignment

    _write_script(tmp_path, monkeypatch, {
        "sessionId": "sess-stable",
        "turns": [
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "implement"}]}},
                       {"name": "produce_artifact",
                        "arguments": {"name": "out", "type": "Document",
                                      "content": "done"}},
                       {"name": "finish", "arguments": {"summary": "done"}}],
             "usage": [100, 20]},
        ],
    })
    # The CLI would write the transcript at the munged-workdir key; simulate it so the
    # exit-time archive has something to copy.
    workdir = stable / "assignments" / a.id / "work"
    transcript = cli_runtime._transcript_path(workdir, "sess-stable")
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"type":"conversation"}', encoding="utf-8")

    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    cli_runtime.cli_tick(agent, cfg)  # intake
    cli_runtime.cli_tick(agent, cfg)  # session
    _wait_session_done(a.id)

    # The tree lives in the stable home; the per-actuation cwd stayed clean.
    assert (workdir / ".mcp.json").is_file()
    assert not (sandbox_cwd / "assignments").exists()
    detail = client.get(f"/api/assignments/{a.id}").json()
    assert detail["assignment"]["transcriptPath"] == str(transcript)
    archived = stable / "assignments" / a.id / "transcripts" / "sess-stable.jsonl"
    assert archived.is_file() and archived.read_text() == '{"type":"conversation"}'


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
    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="Spin")
    node = _node(team, "backend-engineer")
    s = mint_session(team["id"], node_id=node["id"])
    _seed_charter(team, s["actuationId"], node["id"])
    a = get_engine().submit_intent(team["id"], s["actuationId"], "spin regression",
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


def test_gemini_cli_adapter_drives_assignment_and_counts_capacity(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """CAP-D5: cli-gemini compiles .gemini/settings.json + GEMINI.md, parses Gemini stream-json
    (init -> tool_use -> message -> result with stats), settles SpendEvents under provider
    'gemini-cli' at [prices.gemini] rates, and feeds gemini-request-count into google-consumer."""
    from canopy_server.deps import (
        get_capacity_ledger,
        get_db,
        get_engine,
        get_ledger,
        get_profile_store,
        get_provider_accounts,
    )
    from canopy_server.profiles import ProfileParams

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    fake_gemini = Path(__file__).resolve().parent / "fake_gemini.py"
    script_path = tmp_path / "fake_gemini_script.json"
    script_path.write_text(json.dumps({
        "sessionId": "sess-gem-1",
        "turns": [
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "implement"}]}}],
             "usage": [200, 40, 100]},
            {"tools": [{"name": "produce_artifact",
                        "arguments": {"name": "pr", "type": "code-patch",
                                      "content": "gemini diff"}},
                       {"name": "finish",
                        "arguments": {"refs": [], "summary": "done via fake gemini"}}],
             "usage": [300, 60, 50]},
        ],
    }), encoding="utf-8")
    monkeypatch.setenv("FAKE_GEMINI_SCRIPT", str(script_path))
    monkeypatch.setenv("CANOPY_GEMINI_CLI_CMD", json.dumps([sys.executable, str(fake_gemini)]))
    monkeypatch.setenv("CANOPY_CLI_MODEL", "gemini-2.5-pro")

    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="GeminiTeam")
    node = _node(team, "backend-engineer")
    s = mint_session(team["id"], node_id=node["id"])

    # Bind the node to a gemini profile backed by an ai-pro subscription-cli account.
    acct = get_provider_accounts().create(
        provider="gemini", auth_mode="subscription-cli",
        label="Gemini AI Pro (CLI)", plan_hint="ai-pro",
    )
    prof = get_profile_store().create_profile(
        team["id"], name="Gemini Pro", provider="gemini", model="gemini-2.5-pro",
        api_key_secret_id=None, params=ProfileParams(maxOutputTokens=2048),
    )
    with get_db().transaction() as conn:
        conn.execute(
            "UPDATE profiles_profile SET provider_account_id=? WHERE id=?",
            (acct.id, prof.id),
        )
    get_profile_store().set_binding(team["id"], node["id"], prof.id)

    _seed_charter(team, s["actuationId"], node["id"])
    a = get_engine().submit_intent(
        team["id"], s["actuationId"], "ship gemini feature",
        target_node=node["id"], allowance_override=50_000,
    ).assignment

    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    assert cli_runtime.gemini_cli_tick(agent, cfg) == "engaged"  # briefed -> intake-complete
    assert cli_runtime.gemini_cli_tick(agent, cfg) == "engaged"  # planning -> session starts
    _wait_session_done(a.id)

    detail = client.get(f"/api/assignments/{a.id}").json()
    assert detail["assignment"]["state"] == "delivering"
    assert detail["assignment"]["sessionRef"] == "sess-gem-1"

    workdir = tmp_path / "assignments" / a.id / "work"
    gem_settings = json.loads((workdir / ".gemini" / "settings.json").read_text(encoding="utf-8"))
    assert "canopy" in gem_settings["mcpServers"]
    assert "Bash(uv run pytest tests/unit*)" in gem_settings["permissions"]["allow"]
    assert (workdir / "GEMINI.md").is_file()

    # Step settled from Gemini result.stats (500 in, 100 out, 150 cached) under gemini-cli.
    meter = get_ledger().get_meter(a.meterId)
    assert meter.spent == 500 + 100 + int(150 * 0.1)
    with get_db().connect() as conn:
        spend_row = conn.execute(
            "SELECT provider, model, input_tokens, output_tokens, cache_read_tokens, "
            "est_cost_micros FROM ledger_spend_event WHERE task_id = ?",
            (a.id,),
        ).fetchone()
    assert spend_row is not None
    assert spend_row["provider"] == "gemini-cli"
    assert spend_row["model"] == "gemini-2.5-pro"
    assert spend_row["input_tokens"] == 500
    assert spend_row["output_tokens"] == 100
    assert spend_row["cache_read_tokens"] == 150
    assert spend_row["est_cost_micros"] > 0

    # And the local request counter fed google-consumer's cli_daily window.
    w = get_capacity_ledger().window(acct.id, "cli_daily")
    assert w is not None
    assert w["source"] == "inferred"
    assert abs(w["utilization_pct"] - (100.0 * 1 / 1500)) < 0.01


def test_subagent_denial_and_result_usage_reconciliation(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    """Subagent tools (Task, Agent, Subagent, dispatch_agent) are denied by default, and any
    unattributed token burn reported in result.usage / result.modelUsage (e.g. from a nested
    subagent or background model call) is reconciled into a closing Step and charged to the
    salary meter."""
    from canopy_server.deps import get_engine, get_ledger

    monkeypatch.chdir(tmp_path)
    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="Reconcile")
    node = _node(team, "backend-engineer")
    s = mint_session(team["id"], node_id=node["id"])
    _seed_charter(team, s["actuationId"], node["id"])
    # Allowance is 500: the top-level assistant turn burns 180 (under budget), but a hidden
    # subagent in modelUsage burned another 420 -> total 600, which reconciles and trips
    # the hard-stop gate!
    a = get_engine().submit_intent(
        team["id"], s["actuationId"], "no hidden subagent tokens",
        target_node=node["id"], allowance_override=500,
    ).assignment

    _write_script(tmp_path, monkeypatch, {
        "sessionId": "sess-reconcile",
        "turns": [
            {"tools": [{"name": "declare_plan",
                        "arguments": {"stages": [{"title": "implement"}]}}],
             "usage": [150, 30]},
        ],
        "modelUsage": {
            "claude-sonnet-5": {"inputTokens": 150, "outputTokens": 30},
            "claude-haiku-4-5": {"inputTokens": 350, "outputTokens": 70,
                                 "cacheReadInputTokens": 1200},
        },
    })

    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    cli_runtime.cli_tick(agent, cfg)  # intake
    cli_runtime.cli_tick(agent, cfg)  # session
    _wait_session_done(a.id)

    workdir = tmp_path / "assignments" / a.id / "work"
    perms = json.loads((workdir / ".claude" / "settings.json").read_text(encoding="utf-8"))[
        "permissions"
    ]
    for sub_tool in ("Task", "Agent", "Subagent", "dispatch_agent"):
        assert sub_tool in perms["deny"]

    detail = client.get(f"/api/assignments/{a.id}").json()
    reconciled = [st for st in detail["steps"] if st["deltaRef"] == "reconcile:unattributed"]
    assert len(reconciled) == 1
    assert reconciled[0]["inputTokens"] == 350
    assert reconciled[0]["outputTokens"] == 70
    assert reconciled[0]["cacheReadTokens"] == 1200

    # Total meter spend includes both the top-level turn (180) and the reconciled subagent
    # (350 + 70 + int(1200 * 0.1) = 540).
    meter = get_ledger().get_meter(a.meterId)
    assert meter.spent == 180 + 540
    assert detail["assignment"]["state"] == "gated"
    assert any(
        g["state"] == "open" and g["openedBy"] == "trigger:hard-stop"
        for g in detail["gates"]
    )


def test_cli_poll_preserves_operator_notes_for_mcp_get_assignment(
    client, live_server, make_org, mint_session, tmp_path, monkeypatch,
):
    """Polling GET /api/dp/assignment/current from cli_tick (with consume_notes=false) does not
    swallow operator notes before the CLI session calls MCP get_assignment."""
    from canopy_server.deps import get_engine

    monkeypatch.chdir(tmp_path)
    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"})
    node = _node(team, "backend-engineer")
    s = mint_session(team["id"], node_id=node["id"])
    _seed_charter(team, s["actuationId"], node["id"])
    res = get_engine().submit_intent(
        team["id"], s["actuationId"], "Build feature X", target_node=node["id"],
    )
    a = res.assignment

    # Post an operator note before the CLI session runs.
    note_resp = client.post(
        f"/api/intents/{res.intent.id}/notes",
        json={"text": "Use PostgreSQL instead of SQLite.", "assignmentId": a.id},
    )
    assert note_resp.status_code == 201, note_resp.text

    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    # Tick 1 advances briefed -> planning (polling /api/dp/assignment/current
    # with consume_notes=false).
    cli_runtime.cli_tick(agent, cfg)

    # When the LLM inside the CLI session calls MCP `get_assignment`, the note
    # must still be undelivered.
    mcp_resp = client.post(
        "/api/dp/mcp",
        headers={"Authorization": f"Bearer {s['token']}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_assignment", "arguments": {}},
        },
    )
    assert mcp_resp.status_code == 200
    payload = json.loads(mcp_resp.json()["result"]["content"][0]["text"])
    assert len(payload["notes"]) == 1
    assert payload["notes"][0]["text"] == "Use PostgreSQL instead of SQLite."

    # A subsequent MCP `get_assignment` call sees [] because the first MCP call consumed it.
    mcp_resp2 = client.post(
        "/api/dp/mcp",
        headers={"Authorization": f"Bearer {s['token']}"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_assignment", "arguments": {}},
        },
    )
    payload2 = json.loads(mcp_resp2.json()["result"]["content"][0]["text"])
    assert payload2["notes"] == []
