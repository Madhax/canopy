"""Provider breadth (design/organizations/ 03, 04 §5; milestone C6).

The done-bar (07 §1): the fallback chain demo on mock accounts — primary pool
exhausted, the team's profile chain routes the next session to a second account
with headroom — and S4 behind explicit config with the documented posture. Plus
the adversarial extra-usage vectors (house rule 2: NEVER without opt-in + cap
headroom), the park rung's attention notification, google-consumer classification
and counting, and the api-key rate-limit-header windows.
"""

from __future__ import annotations

import json

from canopy_server.capacity.adapters import SessionSignal, WindowReading
from canopy_server.capacity.adapters.anthropic_api import (
    AnthropicApiAdapter,
    readings_from_headers,
)
from canopy_server.capacity.adapters.anthropic_max import AnthropicMaxAdapter
from canopy_server.capacity.adapters.google_consumer import GoogleConsumerAdapter
from test_capacity import FakeClock
from test_economics import _seed_spend, _stack


def _mock_team(client, make_org, mint_session):
    """One team on the shared mock account, with a pre-session root assignment."""
    from canopy_server.deps import get_engine

    team = make_org(name="switcher", seed={"kind": "root", "roleKey": "engineering-lead"})
    root = next(a for a in team["agents"] if a["managerId"] is None)
    s = mint_session(team["id"], node_id=root["id"])
    a = get_engine().submit_intent(team["id"], s["actuationId"], "do the work",
                                   target_node=root["id"]).assignment
    return team, root, s, a


def _second_account(db, profiles, team_id: str, *, model="mock-fallback"):
    """A second pool + a fallback profile pinned to it (the chain's target)."""
    from canopy_server.deps import get_provider_accounts
    from canopy_server.profiles import ProfileParams

    accounts = get_provider_accounts()
    acct_b = accounts.create(provider="mock", auth_mode="mock", label="Mock pool B")
    fallback = profiles.create_profile(
        team_id, name="fallback", provider="mock", model=model,
        api_key_secret_id=None, params=ProfileParams(maxOutputTokens=1024),
    )
    with db.transaction() as conn:
        conn.execute("UPDATE profiles_profile SET provider_account_id=? WHERE id=?",
                     (acct_b.id, fallback.id))
    return acct_b, fallback


def _exhaust(ledger, account_id: str, *, window="mock_window",
             resets="2027-01-01T00:00:00Z"):
    ledger.record_reading(account_id, WindowReading(
        window_key=window, source="provider-event", utilization_pct=100.0,
        resets_at=resets, state_hint="exhausted"))


# --------------------------------------------------------------------------- #
# The done-bar: the fallback chain demo on mock accounts (04 §5 rung 3)
# --------------------------------------------------------------------------- #
def test_switch_account_chain_demo(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db, get_profile_store

    team, root, s, a = _mock_team(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")
    ledger, service, sched = _stack(clock)
    primary = service.account_for_session(team["id"], root["id"])
    acct_b, fallback = _second_account(get_db(), get_profile_store(), team["id"])

    # The chain is per-team opt-in, validated at the API (unknown profiles bounce).
    bad = client.put(f"/api/teams/{team['id']}/schedule",
                     json={"profileChain": ["ap_nope"]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "BAD_PROFILE_CHAIN"
    r = client.put(f"/api/teams/{team['id']}/schedule", json={
        "fallbackPolicy": ["hold-resume", "switch-account"],
        "profileChain": [fallback.id],
    })
    assert r.status_code == 200 and r.json()["schedule"]["profileChain"] == [fallback.id]

    # Primary pool dies → the ladder routes the next session to pool B, fresh.
    _exhaust(ledger, primary.id)
    admission = sched.check(team["id"], root["id"], a)
    assert admission.admit is True and admission.reason == "switch-account"
    assert admission.profile_override["accountId"] == acct_b.id
    assert admission.profile_override["model"] == "mock-fallback"
    assert admission.profile_override["profileId"] == fallback.id

    # The engagement is on the feed — nothing the ladder does is invisible (06 §4).
    events = ledger.events(primary.id)
    (engaged,) = [e for e in events if e["kind"] == "fallback-engaged"]
    assert engaged["payload"]["rung"] == "switch-account"
    assert engaged["payload"]["toAccountId"] == acct_b.id

    # Both pools shut → the chain has no headroom → hold-resume, honestly.
    _exhaust(ledger, acct_b.id)
    held = sched.check(team["id"], root["id"], a)
    assert held.admit is False and held.reason == "window-exhausted"


def test_switch_account_rides_the_dp(client, make_org, mint_session, monkeypatch):
    """The runtime's view: assignment/current carries the fresh-session override."""
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from fastapi.testclient import TestClient

    from canopy_server.deps import (
        get_capacity_ledger,
        get_capacity_service,
        get_db,
        get_profile_store,
    )
    from canopy_server.main import app

    team, root, s, a = _mock_team(client, make_org, mint_session)
    primary = get_capacity_service().account_for_session(team["id"], root["id"])
    acct_b, fallback = _second_account(get_db(), get_profile_store(), team["id"])
    client.put(f"/api/teams/{team['id']}/schedule", json={
        "fallbackPolicy": ["switch-account"], "profileChain": [fallback.id]})
    _exhaust(get_capacity_ledger(), primary.id)

    agent = TestClient(app, headers={"Authorization": f"Bearer {s['token']}"})
    cur = agent.get("/api/dp/assignment/current").json()
    assert "hold" not in cur
    assert cur["profileOverride"]["accountId"] == acct_b.id
    assert cur["profileOverride"]["model"] == "mock-fallback"
    assert cur["extraUsage"] is False


# --------------------------------------------------------------------------- #
# Extra usage (04 §5 rung 4, K10) — adversarial: opt-in + headroom or NOTHING
# --------------------------------------------------------------------------- #
def test_extra_usage_never_engages_without_opt_in(client, make_org, mint_session,
                                                  monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    team, root, s, a = _mock_team(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")
    ledger, service, sched = _stack(clock)
    account = service.account_for_session(team["id"], root["id"])
    _exhaust(ledger, account.id)

    def admission():
        return sched.check(team["id"], root["id"], a)

    # Rung configured, NO cap on the account: hold. (No opt-in, no credits.)
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"fallbackPolicy": ["extra-usage"]})
    assert admission().reason == "window-exhausted"

    # Cap set, rung NOT configured: hold. (The team never asked for the ladder.)
    with get_db().transaction() as conn:
        conn.execute("UPDATE provider_account SET extra_usage_cap_usd=5.0 WHERE id=?",
                     (account.id,))
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"fallbackPolicy": ["hold-resume"]})
    assert admission().reason == "window-exhausted"

    # Opt-in + headroom: engages, flagged.
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"fallbackPolicy": ["extra-usage"]})
    engaged = admission()
    assert engaged.admit is True and engaged.reason == "extra-usage"
    assert engaged.extra_usage is True

    # Tracked claude-extra spend reaches the cap: the door closes again.
    _seed_spend(get_db(), team["id"], 6.0, clock(), "extra")
    with get_db().transaction() as conn:
        conn.execute(
            "UPDATE ledger_spend_event SET provider='claude-extra', node_id=?"
            " WHERE id=?", (root["id"], f"sp_{team['id']}_extra"))
    assert admission().reason == "window-exhausted"


def test_extra_usage_steps_are_tagged_claude_extra(client, make_org, mint_session,
                                                   monkeypatch):
    """The money tag (06 §6.5): settled spend while engaged lands as
    provider='claude-extra' — server-decided, agents stay ignorant."""
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    import sys
    from pathlib import Path

    _AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
    if str(_AGENT_SRC) not in sys.path:
        sys.path.insert(0, str(_AGENT_SRC))
    from canopy_agent.runtime import AgentConfig, loop_tick
    from fastapi.testclient import TestClient

    from canopy_server.deps import get_capacity_ledger, get_capacity_service, get_db
    from canopy_server.main import app

    team, root, s, a = _mock_team(client, make_org, mint_session)
    agent = TestClient(app, headers={"Authorization": f"Bearer {s['token']}"})
    cfg = AgentConfig(cp_url="http://cp", run_token=s["token"], node_id=root["id"],
                      actuation_id=s["actuationId"], a2a_host="127.0.0.1", a2a_port=0)
    for _ in range(3):
        loop_tick(agent, cfg)
    account = get_capacity_service().account_for_session(team["id"], root["id"])
    with get_db().transaction() as conn:
        conn.execute("UPDATE provider_account SET extra_usage_cap_usd=5.0 WHERE id=?",
                     (account.id,))
    client.put(f"/api/teams/{team['id']}/schedule",
               json={"fallbackPolicy": ["extra-usage"]})
    _exhaust(get_capacity_ledger(), account.id)

    r = agent.post("/api/dp/assignment/events", json={
        "assignmentId": a.id, "kind": "step", "stepKind": "production",
        "inputTokens": 100, "outputTokens": 50, "durationMs": 10,
        "settle": True, "model": "claude-sonnet-5", "stepId": "st_extra_1",
    })
    assert r.status_code == 200, r.text
    with get_db().connect() as conn:
        row = conn.execute(
            "SELECT provider, est_cost_micros FROM ledger_spend_event WHERE step_id=?",
            ("st_extra_1",)).fetchone()
    assert row is not None and row["provider"] == "claude-extra"
    assert row["est_cost_micros"] > 0  # money, never a "$0" subscription row


# --------------------------------------------------------------------------- #
# Park (04 §5 rung 5): drain + the attention notification (06 §5)
# --------------------------------------------------------------------------- #
def test_park_drains_and_pages(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    team, root, s, a = _mock_team(client, make_org, mint_session)
    # The app-wired scheduler carries the notify hook; exhaust via the real ledger.
    from canopy_server.deps import get_capacity_ledger, get_capacity_service, get_scheduler

    account = get_capacity_service().account_for_session(team["id"], root["id"])
    _exhaust(get_capacity_ledger(), account.id)
    client.put(f"/api/teams/{team['id']}/schedule", json={"fallbackPolicy": ["park"]})

    held = get_scheduler().check(team["id"], root["id"], a)
    assert held.admit is False and held.reason == "park"
    assert client.get(f"/api/teams/{team['id']}/schedule").json()["schedule"]["runState"] \
        == "drain"
    notes = client.get(f"/api/teams/{team['id']}/notifications").json()["notifications"]
    (note,) = [n for n in notes if n["kind"] == "capacity-parked"]
    assert note["severity"] == "attention"
    # Idempotent under polling: a second check re-holds without a second page.
    get_scheduler().check(team["id"], root["id"], a)
    notes = client.get(f"/api/teams/{team['id']}/notifications").json()["notifications"]
    assert len([n for n in notes if n["kind"] == "capacity-parked"]) == 1


# --------------------------------------------------------------------------- #
# S4 — behind explicit config, with the documented posture (03 §2)
# --------------------------------------------------------------------------- #
_S4_PAYLOAD = {
    "five_hour": {"utilization": 82.0, "resets_at": 1789200000},
    "seven_day": {"utilization": 31.0, "resets_at": "2026-08-17T09:00:00Z"},
    "seven_day_opus": {"utilization": 56.0, "resets_at": "2026-08-17T09:00:00Z"},
    "seven_day_sonnet": {"utilization": 12.5, "resets_at": "2026-08-17T09:00:00Z"},
    "extra_usage": {"is_enabled": True, "monthly_limit": 200, "used_credits": 37,
                    "utilization": 18.5},
    "some_future_key": {"whatever": 1},
}


def test_s4_parses_the_full_window_set(tmp_path):
    from canopy_server.capacity.adapters.anthropic_usage import parse_usage_payload

    readings = parse_usage_payload(_S4_PAYLOAD)
    by_key = {r.window_key: r for r in readings}
    assert set(by_key) == {"five_hour", "seven_day", "seven_day_opus",
                           "seven_day_sonnet", "extra_usage"}
    assert all(r.source == "provider-read" for r in readings)
    assert by_key["five_hour"].utilization_pct == 82.0
    assert by_key["five_hour"].resets_at.endswith("Z")  # epoch → ISO
    assert by_key["extra_usage"].kind == "credit-pool"
    assert "37/200" in by_key["extra_usage"].detail


def test_s4_is_off_by_default_and_gated_by_config(tmp_path, monkeypatch):
    """The compliance posture is the operator's explicit call: source='observed'
    (the default) polls NOTHING even with credentials on disk."""
    import canopy_server.config as config
    from canopy_server.capacity.accounts import ProviderAccount
    from canopy_server.capacity.adapters import anthropic_usage

    (tmp_path / ".credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "tok-123"}}), encoding="utf-8")
    account = ProviderAccount(id="pa_t", provider="anthropic",
                              authMode="subscription-cli", label="Max",
                              cliConfigDir=str(tmp_path))
    adapter = AnthropicMaxAdapter()
    assert config.get_capacity_anthropic_source() == "observed"  # the default
    assert adapter.poll(account) == []

    # Explicit opt-in: the poll delegates to the isolated S4 module.
    monkeypatch.setattr(config, "get_capacity_anthropic_source",
                        lambda: "usage-endpoint")
    monkeypatch.setattr(anthropic_usage, "_default_fetcher",
                        lambda url, headers: _S4_PAYLOAD)
    readings = adapter.poll(account)
    assert {r.window_key for r in readings} >= {"five_hour", "seven_day"}
    # And the etiquette floor holds no matter what the toml says.
    assert config.get_capacity_anthropic_poll_s() >= 180


def test_s4_degrades_soft(tmp_path):
    from canopy_server.capacity.accounts import ProviderAccount
    from canopy_server.capacity.adapters.anthropic_usage import (
        fetch_usage,
        read_oauth_token,
    )

    assert read_oauth_token(str(tmp_path)) is None  # no credentials file
    (tmp_path / ".credentials.json").write_text("not json", encoding="utf-8")
    assert read_oauth_token(str(tmp_path)) is None  # unparseable → None, no raise
    (tmp_path / ".credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "tok-123"}}), encoding="utf-8")
    assert read_oauth_token(str(tmp_path)) == "tok-123"

    account = ProviderAccount(id="pa_t", provider="anthropic",
                              authMode="subscription-cli", label="Max",
                              cliConfigDir=str(tmp_path))

    def boom(url, headers):
        raise OSError("429 or network — either way, degrade")

    assert fetch_usage(account, fetcher=boom) == []  # [Community] surfaces fail soft


def test_extra_usage_window_seeds_only_when_opted_in():
    from canopy_server.capacity.accounts import ProviderAccount

    adapter = AnthropicMaxAdapter()
    plain = ProviderAccount(id="pa_a", provider="anthropic",
                            authMode="subscription-cli", label="Max")
    opted = plain.model_copy(update={"extraUsageCapUsd": 25.0})
    assert "extra_usage" not in {w.key for w in adapter.expected_windows(plain)}
    assert "extra_usage" in {w.key for w in adapter.expected_windows(opted)}


# --------------------------------------------------------------------------- #
# google-consumer — classification + the counting schema (03 §3, CAP-D5)
# --------------------------------------------------------------------------- #
def _gacct(plan="ai-pro"):
    from canopy_server.capacity.accounts import ProviderAccount

    return ProviderAccount(id="pa_g", provider="google", authMode="subscription-cli",
                           label="Google AI", planHint=plan)


def test_google_classification_vectors():
    adapter = GoogleConsumerAdapter()
    acct = _gacct()
    daily = ('429 RESOURCE_EXHAUSTED: QuotaFailure '
             '{"quotaId": "GenerateRequestsPerDayPerProjectPerModel"}')
    minute = "429 RESOURCE_EXHAUSTED: quota GenerateRequestsPerMinute exceeded"
    assert adapter.classify_error(acct, daily) == "quota-exhausted"
    assert adapter.classify_error(acct, minute) == "capacity-transient"
    assert adapter.classify_error(acct, "429: no capacity for model gemini-3-pro") \
        == "capacity-transient"
    assert adapter.classify_error(acct, "UNAUTHENTICATED: please login") == "auth"
    # Indistinguishable stays transient — no invented precision.
    assert adapter.classify_error(acct, "RESOURCE_EXHAUSTED") == "capacity-transient"


def test_google_counts_against_the_published_denominator():
    adapter = GoogleConsumerAdapter()
    (reading,) = adapter.on_session_event(_gacct("ai-pro"), SessionSignal(
        signal="gemini-request-count",
        payload={"countToday": 287, "observedAt": "2026-08-12T12:00:00Z"}))
    assert reading.source == "inferred"  # counted locally, never provider truth
    assert reading.window_key == "cli_daily"
    assert abs(reading.utilization_pct - 100.0 * 287 / 1500) < 0.01
    assert reading.detail == "counted-locally 287/1500"
    # Midnight PT on the provider's clock (07:00Z in PDT; 08:00Z if no tzdata).
    assert reading.resets_at in ("2026-08-13T07:00:00Z", "2026-08-13T08:00:00Z")

    # Unknown plan → no denominator → NO reading (unknown beats fabricated).
    assert adapter.on_session_event(_gacct(None), SessionSignal(
        signal="gemini-request-count", payload={"countToday": 10})) == []


def test_google_daily_exhaustion_pins_the_window():
    adapter = GoogleConsumerAdapter()
    (reading,) = adapter.on_session_event(_gacct(), SessionSignal(
        signal="session-result",
        text='RESOURCE_EXHAUSTED: QuotaFailure {"quotaId": "RequestsPerDay"}',
        payload={"observedAt": "2026-08-12T12:00:00Z"}))
    assert reading.state_hint == "exhausted" and reading.window_key == "cli_daily"
    assert reading.source == "provider-event"
    # RetryInfo is documented-unreliable for daily exhaustion: the reset is
    # midnight PT, computed, not the payload's retryDelay.
    assert reading.resets_at in ("2026-08-13T07:00:00Z", "2026-08-13T08:00:00Z")


# --------------------------------------------------------------------------- #
# anthropic api-key — token buckets from rate-limit headers (03 §2 tail)
# --------------------------------------------------------------------------- #
def test_api_key_header_windows():
    headers = {
        "Anthropic-Ratelimit-Requests-Limit": "50",
        "Anthropic-Ratelimit-Requests-Remaining": "37",
        "Anthropic-Ratelimit-Requests-Reset": "2026-08-12T12:01:00Z",
        "anthropic-ratelimit-input-tokens-limit": "40000",
        "anthropic-ratelimit-input-tokens-remaining": "10000",
        "anthropic-ratelimit-input-tokens-reset": "2026-08-12T12:01:00Z",
        "anthropic-ratelimit-output-tokens-limit": "0",  # zero limit: no reading
    }
    readings = readings_from_headers(headers)
    by_key = {r.window_key: r for r in readings}
    assert set(by_key) == {"requests_min", "input_tokens_min"}
    assert by_key["requests_min"].utilization_pct == 26.0  # (50-37)/50, case-blind
    assert by_key["input_tokens_min"].utilization_pct == 75.0
    assert by_key["requests_min"].resets_at == "2026-08-12T12:01:00Z"
    assert all(r.source == "provider-read" and r.kind == "token-bucket"
               for r in readings)


def test_api_key_adapter_signal_and_classification():
    from canopy_server.capacity.accounts import ProviderAccount

    adapter = AnthropicApiAdapter()
    acct = ProviderAccount(id="pa_k", provider="anthropic", authMode="api-key",
                           label="Anthropic api-key")
    (reading,) = adapter.on_session_event(acct, SessionSignal(
        signal="response-headers",
        payload={"headers": {"anthropic-ratelimit-requests-limit": "10",
                             "anthropic-ratelimit-requests-remaining": "0"}}))
    assert reading.window_key == "requests_min" and reading.utilization_pct == 100.0
    # A bucket 429 is pressure, not a shut window (buckets refill in seconds).
    assert adapter.classify_error(acct, "429 rate_limit_error") == "capacity-transient"
    assert adapter.classify_error(acct, "401 invalid x-api-key") == "auth"
    assert {w.key for w in adapter.expected_windows(acct)} \
        == {"requests_min", "input_tokens_min", "output_tokens_min"}


# --------------------------------------------------------------------------- #
# Accounts API — the K10 cap is operator data, settable and clearable
# --------------------------------------------------------------------------- #
def test_account_extra_usage_cap_crud(client):
    r = client.post("/api/capacity/accounts", json={
        "provider": "anthropic", "authMode": "subscription-cli",
        "label": "Max (patrick)", "extraUsageCapUsd": 25.0})
    assert r.status_code == 201 and r.json()["extraUsageCapUsd"] == 25.0
    acct_id = r.json()["id"]
    r = client.put(f"/api/capacity/accounts/{acct_id}", json={"extraUsageCapUsd": 40.0})
    assert r.json()["extraUsageCapUsd"] == 40.0
    # Negative clears — extra usage is OFF again for this account.
    r = client.put(f"/api/capacity/accounts/{acct_id}", json={"extraUsageCapUsd": -1})
    assert r.json()["extraUsageCapUsd"] is None
