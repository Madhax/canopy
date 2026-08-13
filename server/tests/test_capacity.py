"""The C2 capacity substrate (design/organizations/02–03).

The done-bar (07 §1): the fake-CLI limit script drives a window ``exhausted`` → ``ok``
through readings, and attribution splits two mock teams correctly under a test clock.
Every displayed number carries its tier; the clock is injected, never ``now()``-scattered.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from canopy_server.capacity.accounts import ProviderAccountStore
from canopy_server.capacity.adapters import SessionSignal, adapter_for
from canopy_server.capacity.adapters.anthropic_max import AnthropicMaxAdapter, parse_limit_text
from canopy_server.capacity.ledger import CapacityLedger
from canopy_server.db import Db


class FakeClock:
    """The injected clock (07 §6): capacity math must be clock-driven, never wall-time."""

    def __init__(self, start: str = "2026-08-10T12:00:00Z"):
        self.now = datetime.fromisoformat(start.replace("Z", "+00:00"))

    def __call__(self) -> str:
        return self.now.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def db(tmp_path) -> Db:
    return Db(tmp_path / "canopy.db")


@pytest.fixture()
def ledger(db, clock) -> CapacityLedger:
    return CapacityLedger(db, now=clock, reading_ttl_s=900, attribution_window_s=3600)


@pytest.fixture()
def accounts(db, clock) -> ProviderAccountStore:
    return ProviderAccountStore(db, now=clock)


# --------------------------------------------------------------------------- #
# S1 parsing — golden vectors for both known shapes (03 §2)
# --------------------------------------------------------------------------- #
def test_s1_pipe_shape_parses_epoch():
    r = parse_limit_text("Claude AI usage limit reached|1754899200")
    assert r is not None and r.window_key == "five_hour"
    assert r.utilization_pct == 100.0 and r.state_hint == "exhausted"
    assert r.resets_at == "2025-08-11T08:00:00+00:00".replace("+00:00", "Z") or \
        r.resets_at.endswith("Z")


@pytest.mark.parametrize("text,window", [
    ("You've hit your session limit · resets 3:45pm", "five_hour"),
    ("You've hit your weekly limit · resets Tuesday", "seven_day"),
    ("You've hit your Opus weekly limit", "seven_day_opus"),
])
def test_s1_interactive_shapes(text, window):
    r = parse_limit_text(text)
    assert r is not None and r.window_key == window
    assert r.utilization_pct == 100.0
    # The human phrasing carries no full timestamp — the reset stays honestly unknown.
    assert r.resets_at is None


def test_s1_generic_limit_text_degrades_conservatively():
    r = parse_limit_text("Some new phrasing: usage limit reached, try later")
    assert r is not None and r.window_key == "five_hour" and r.resets_at is None


def test_s1_non_limit_text_is_not_a_reading():
    assert parse_limit_text("TypeError: cannot read properties of undefined") is None


def test_classify_error_tiers(accounts):
    adapter = AnthropicMaxAdapter()
    acct = accounts.ensure_cli_account()
    assert adapter.classify_error(acct, "Claude AI usage limit reached|1754899200") \
        == "quota-exhausted"
    assert adapter.classify_error(acct, "overloaded_error: try again") \
        == "capacity-transient"
    assert adapter.classify_error(acct, "Invalid API key · please run /login") == "auth"
    assert adapter.classify_error(acct, "segfault") == "other"


# --------------------------------------------------------------------------- #
# Reading precedence — most authoritative recent, never merely newest (02 §4)
# --------------------------------------------------------------------------- #
def _reading(key="five_hour", source="provider-read", util=None, resets=None, hint=None):
    from canopy_server.capacity.adapters import WindowReading

    return WindowReading(window_key=key, source=source, utilization_pct=util,
                         resets_at=resets, state_hint=hint)


def test_fresh_tier1_beats_tier2(ledger, accounts, clock):
    acct = accounts.ensure_cli_account()
    ledger.record_reading(acct.id, _reading(util=42.0, source="provider-read"))
    clock.advance(60)
    ledger.record_reading(acct.id, _reading(source="provider-event", hint="ok"))
    w = ledger.window(acct.id, "five_hour")
    assert w["source"] == "provider-read" and w["utilization_pct"] == 42.0


def test_stale_tier1_yields_to_tier2(ledger, accounts, clock):
    acct = accounts.ensure_cli_account()
    ledger.record_reading(acct.id, _reading(util=42.0, source="provider-read"))
    clock.advance(1000)  # past reading_ttl_s
    ledger.record_reading(acct.id, _reading(source="provider-event", util=100.0,
                                            hint="exhausted"))
    w = ledger.window(acct.id, "five_hour")
    assert w["source"] == "provider-event" and w["state"] == "exhausted"


def test_inferred_never_overrides_fresh_anchor(ledger, accounts, clock):
    acct = accounts.ensure_cli_account()
    ledger.record_reading(acct.id, _reading(util=42.0, source="provider-read"))
    clock.advance(30)
    ledger.record_reading(acct.id, _reading(util=90.0, source="inferred"))
    w = ledger.window(acct.id, "five_hour")
    assert w["utilization_pct"] == 42.0 and w["source"] == "provider-read"


def test_exhausted_decays_to_ok_when_reset_passes(ledger, accounts, clock):
    acct = accounts.ensure_cli_account()
    resets = "2026-08-10T13:00:00Z"
    ledger.record_reading(acct.id, _reading(util=100.0, source="provider-event",
                                            resets=resets, hint="exhausted"))
    assert ledger.window(acct.id, "five_hour")["state"] == "exhausted"
    clock.advance(3601)  # past the provider's reset
    w = ledger.window(acct.id, "five_hour")
    assert w["state"] == "ok" and w["utilization_pct"] is None  # level honestly unknown


def test_every_window_view_carries_tier_and_age(ledger, accounts, clock):
    acct = accounts.ensure_cli_account()
    ledger.record_reading(acct.id, _reading(util=61.5))
    clock.advance(180)
    w = ledger.window(acct.id, "five_hour")
    assert w["source"] == "provider-read" and w["age_s"] == 180


# --------------------------------------------------------------------------- #
# The done-bar: fake-CLI limit script → exhausted → ok, through readings
# --------------------------------------------------------------------------- #
def _run_fake_cli(tmp_path, script: dict) -> list[dict]:
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    fake = Path(__file__).parent / "fake_claude.py"
    env = {**os.environ, "FAKE_CLAUDE_SCRIPT": str(script_path)}
    out = subprocess.run([sys.executable, str(fake), "-p", "work"],
                         capture_output=True, text=True, env=env)
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def _signals_from_stream(events: list[dict]) -> list[SessionSignal]:
    """Exactly the cli-adapter's forwarding rule (S1/S2), applied to a captured stream."""
    signals = []
    for ev in events:
        if ev.get("type") == "system" and ev.get("subtype") == "api_retry":
            signals.append(SessionSignal(signal="api_retry", error=ev.get("error"),
                                         error_status=ev.get("error_status"),
                                         retry_delay_ms=ev.get("retry_delay_ms")))
        elif ev.get("type") == "result":
            if ev.get("is_error"):
                signals.append(SessionSignal(signal="session-result",
                                             text=str(ev.get("result", ""))))
            else:
                signals.append(SessionSignal(signal="session-ok"))
    return signals


def test_fake_cli_limit_script_drives_exhausted_then_ok(tmp_path, db, clock):
    accounts = ProviderAccountStore(db, now=clock)
    ledger = CapacityLedger(db, now=clock)
    acct = accounts.ensure_cli_account()
    adapter = adapter_for(acct)
    reset_epoch = int(clock.now.timestamp()) + 1800  # provider says: resets in 30 min

    # Session 1: the limit script — the CLI dies with the S1 pipe shape.
    events = _run_fake_cli(tmp_path, {
        "turns": [{"usage": [100, 20],
                   "apiRetry": {"error": "rate_limit", "error_status": 429,
                                "retry_delay_ms": 900}}],
        "limitResult": f"Claude AI usage limit reached|{reset_epoch}",
    })
    for sig in _signals_from_stream(events):
        for reading in adapter.on_session_event(acct, sig):
            ledger.record_reading(acct.id, reading)
    w = ledger.window(acct.id, "five_hour")
    assert w["state"] == "exhausted" and w["utilization_pct"] == 100.0
    assert w["resets_at"] is not None

    # The provider's reset passes; a clean session confirms the door is open.
    clock.advance(1801)
    events = _run_fake_cli(tmp_path, {"turns": [{"usage": [50, 10]}]})
    for sig in _signals_from_stream(events):
        for reading in adapter.on_session_event(acct, sig):
            ledger.record_reading(acct.id, reading)
    w = ledger.window(acct.id, "five_hour")
    assert w["state"] == "ok"


# --------------------------------------------------------------------------- #
# Attribution — two teams, one window, a test clock (02 §5)
# --------------------------------------------------------------------------- #
def _seed_steps(db, team_id: str, tokens: int, at: str) -> None:
    aid = f"as_{team_id}_{at[-6:-1]}"
    with db.transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO work_assignment (id, team_id, actuation_id, intent_id,"
            " node_id, issued_by, state, contract_kind, contract_type, created_at,"
            " updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (aid, team_id, "act_x", "in_x", "a_x", "operator", "executing", "artifact",
             "Doc", at, at),
        )
        conn.execute(
            "INSERT INTO work_step (id, assignment_id, kind, input_tokens, output_tokens,"
            " duration_ms, created_at) VALUES (?,?,?,?,?,?,?)",
            (f"st_{team_id}_{at[-6:-1]}", aid, "production", tokens, 0, 10, at),
        )


def test_attribution_splits_two_teams_and_sums_to_delta(db, clock, accounts, ledger):
    acct = accounts.ensure_mock_account()
    since = clock()
    ledger.record_reading(acct.id, _reading(key="mock_window", util=60.0))
    clock.advance(600)
    _seed_steps(db, "team-a", 3000, clock())
    _seed_steps(db, "team-b", 1000, clock())
    clock.advance(600)
    ledger.record_reading(acct.id, _reading(key="mock_window", util=70.0))

    attr = ledger.attribution(acct.id, "mock_window", since=since)
    assert attr["deltaPct"] == pytest.approx(10.0)
    # Split follows Canopy's own step metering: 3:1.
    assert attr["teams"]["team-a"] == pytest.approx(7.5)
    assert attr["teams"]["team-b"] == pytest.approx(2.5)
    # Money-path paranoia, extended to capacity: shares + external ≡ provider delta.
    assert sum(attr["teams"].values()) + attr["external"] == pytest.approx(attr["deltaPct"])


def test_attribution_with_no_canopy_steps_is_all_external(db, clock, accounts, ledger):
    acct = accounts.ensure_mock_account()
    since = clock()
    ledger.record_reading(acct.id, _reading(key="mock_window", util=10.0))
    clock.advance(1200)
    ledger.record_reading(acct.id, _reading(key="mock_window", util=25.0))
    attr = ledger.attribution(acct.id, "mock_window", since=since)
    assert attr["teams"] == {} and attr["external"] == pytest.approx(15.0)


def test_resets_never_count_as_negative_burn(db, clock, accounts, ledger):
    acct = accounts.ensure_mock_account()
    since = clock()
    for util in (80.0, 95.0, 5.0, 20.0):  # a reset (95→5) then fresh burn
        ledger.record_reading(acct.id, _reading(key="mock_window", util=util))
        clock.advance(300)
    attr = ledger.attribution(acct.id, "mock_window", since=since)
    assert attr["deltaPct"] == pytest.approx(30.0)  # 15 + 15, the drop ignored


def test_runway_from_burn(db, clock, accounts, ledger):
    acct = accounts.ensure_mock_account()
    ledger.record_reading(acct.id, _reading(key="mock_window", util=40.0))
    clock.advance(1800)
    _seed_steps(db, "team-a", 2000, clock())
    clock.advance(1700)
    ledger.record_reading(acct.id, _reading(key="mock_window", util=75.0))
    runway = ledger.runway(acct.id, "mock_window")
    assert runway["exhaustsAt"] is not None and runway["burnPpHr"] > 0


# --------------------------------------------------------------------------- #
# The §2.3 migration — profiles split into accounts, idempotently
# --------------------------------------------------------------------------- #
def _seed_profile(db, pid, provider, secret, at="2026-08-10T11:00:00Z"):
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO profiles_profile (id, team_id, name, provider, model,"
            " api_key_secret_id, params, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, "t1", pid, provider, "m", secret, "{}", at, at),
        )


def test_profile_to_account_migration(db, clock):
    # The profiles table must exist before the migration runs.
    from canopy_server import profiles  # noqa: F401
    db.ensure_schema()
    _seed_profile(db, "ap_1", "anthropic", "sec_A")
    _seed_profile(db, "ap_2", "anthropic", "sec_A")  # same secret → same account
    _seed_profile(db, "ap_3", "anthropic", "sec_B")
    _seed_profile(db, "ap_4", "mock", None)
    store = ProviderAccountStore(db, now=clock)

    accounts = store.list()
    by_mode = {}
    for a in accounts:
        by_mode.setdefault(a.authMode, []).append(a)
    assert len(by_mode.get("api-key", [])) == 2  # sec_A, sec_B — deduped
    assert len(by_mode.get("mock", [])) == 1
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, provider_account_id FROM profiles_profile ORDER BY id"
        ).fetchall()
    stamped = {r["id"]: r["provider_account_id"] for r in rows}
    assert all(stamped.values())
    assert stamped["ap_1"] == stamped["ap_2"] != stamped["ap_3"]

    # Idempotent: a second construction creates nothing new.
    ProviderAccountStore(db, now=clock)
    assert len(ProviderAccountStore(db, now=clock).list()) == len(accounts)


# --------------------------------------------------------------------------- #
# The wire: a dp limit-signal lands in the ledger (mock spine, capacity enabled)
# --------------------------------------------------------------------------- #
def test_dp_limit_signal_reaches_ledger(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = next(a for a in team["agents"] if a["managerId"] is None)
    s = mint_session(team["id"], node_id=root["id"])
    from canopy_server.deps import get_engine

    a = get_engine().submit_intent(team["id"], s["actuationId"], "work",
                                   target_node=root["id"]).assignment
    r = client.post(
        "/api/dp/assignment/events",
        headers={"Authorization": f"Bearer {s['token']}"},
        json={"assignmentId": a.id, "kind": "limit-signal", "signal": "mock-reading",
              "payload": {"windowKey": "mock_window", "utilizationPct": 55.0,
                          "source": "provider-read"}},
    )
    assert r.status_code == 200, r.text
    from canopy_server.deps import get_capacity_ledger, get_provider_accounts

    acct = get_provider_accounts().find("mock", "mock")
    assert acct is not None
    w = get_capacity_ledger().window(acct.id, "mock_window")
    assert w is not None and w["utilization_pct"] == 55.0 and w["source"] == "provider-read"


# --------------------------------------------------------------------------- #
# C3 — the read surface: aggregate honesty, the S3 tap, capacity notifications
# --------------------------------------------------------------------------- #
def _signal(client, s, aid, payload):
    return client.post(
        "/api/dp/assignment/events",
        headers={"Authorization": f"Bearer {s['token']}"},
        json={"assignmentId": aid, "kind": "limit-signal", **payload},
    )


def test_capacity_aggregate_wears_source_and_age(client, make_org, mint_session,
                                                 monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = next(a for a in team["agents"] if a["managerId"] is None)
    s = mint_session(team["id"], node_id=root["id"])
    from canopy_server.deps import get_engine

    a = get_engine().submit_intent(team["id"], s["actuationId"], "work",
                                   target_node=root["id"]).assignment
    r = _signal(client, s, a.id, {"signal": "mock-reading",
                "payload": {"windowKey": "mock_window", "utilizationPct": 61.0,
                            "source": "provider-read"}})
    assert r.status_code == 200

    agg = client.get("/api/capacity").json()
    assert agg["enabled"] is True
    (acct,) = [x for x in agg["accounts"] if x["provider"] == "mock"]
    (w,) = [x for x in acct["windows"] if x["key"] == "mock_window"]
    # The honesty rule: every level wears its tier and its age (06 §6.1).
    assert w["utilizationPct"] == 61.0 and w["source"] == "provider-read"
    assert w["ageS"] is not None
    # The event feed carries the reading with its team attached.
    assert any(ev["kind"] == "window-reading" and ev["teamId"] == team["id"]
               for ev in acct["events"])


def test_expected_windows_render_no_reading_never_zero(client, make_org, mint_session,
                                                       monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_provider_accounts

    get_provider_accounts().ensure_cli_account("anthropic")
    agg = client.get("/api/capacity").json()
    (acct,) = [x for x in agg["accounts"] if x["authMode"] == "subscription-cli"]
    by_key = {w["key"]: w for w in acct["windows"]}
    # planHint/adapter seeds the gauges; unknown beats fabricated (06 §6.3).
    assert "five_hour" in by_key and "seven_day_opus" in by_key
    assert by_key["five_hour"]["state"] == "unknown"
    assert by_key["five_hour"]["utilizationPct"] is None  # never 0%, never a guess


def test_statusline_tap_records_tier1_readings(client, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    r = client.post("/api/capacity/statusline", json={
        "rate_limits": {
            "five_hour": {"used_percentage": 82.0, "resets_at": 1754899200},
            "seven_day": {"used_percentage": 31.0, "resets_at": 1755100800},
        }
    })
    assert r.status_code == 200 and r.json()["readings"] == 2
    from canopy_server.deps import get_capacity_ledger, get_provider_accounts

    acct = get_provider_accounts().find("anthropic", "subscription-cli")
    w = get_capacity_ledger().window(acct.id, "five_hour")
    assert w["utilization_pct"] == 82.0 and w["source"] == "provider-read"
    assert w["resets_at"].endswith("Z")


def test_statusline_tap_disabled_when_capacity_off(client, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "0")
    r = client.post("/api/capacity/statusline", json={"rate_limits": {}})
    assert r.status_code == 409


def test_exhaustion_emits_info_notification_once(client, make_org, mint_session,
                                                 monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = next(a for a in team["agents"] if a["managerId"] is None)
    s = mint_session(team["id"], node_id=root["id"])
    from canopy_server.deps import get_engine

    a = get_engine().submit_intent(team["id"], s["actuationId"], "work",
                                   target_node=root["id"]).assignment
    payload = {"signal": "mock-reading",
               "payload": {"windowKey": "mock_window", "utilizationPct": 100.0,
                           "source": "provider-event", "stateHint": "exhausted",
                           "resetsAt": "2027-01-01T00:00:00Z"}}
    _signal(client, s, a.id, payload)
    _signal(client, s, a.id, payload)  # a signal storm is one notification (dedupe)

    notes = client.get(f"/api/teams/{team['id']}/notifications").json()["notifications"]
    cap = [n for n in notes if n["kind"] == "capacity-exhausted"]
    # Exhaustion is NOT an emergency (06 §5): info severity, the governor handles it.
    assert len(cap) == 1 and cap[0]["severity"] == "info"
