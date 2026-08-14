"""Org economics + fairness (design/organizations/ 01 §6, 04 §6; milestone C5).

The done-bar (07 §1): the SC-5 scenario as a scheduler test — two orgs on one
contended mock pool, shares honored under contention (an org with pent-up demand
accumulates claim while idle), and the K8 reserve admitting the interactive team
at high utilization. Plus: the org weekly ceiling at intent admission (warn, then
refuse; running work untouched), budget validation, and the what-if strip's math.

The FakeClock gotcha from C4 holds: ledger + service + scheduler are always built
on ONE clock, so window decay, attribution horizons, and admission agree.
"""

from __future__ import annotations

from canopy_server.capacity.adapters import WindowReading
from canopy_server.capacity.ledger import CapacityLedger
from canopy_server.capacity.service import CapacityService
from canopy_server.scheduler import Scheduler
from test_capacity import FakeClock


def _stack(clock: FakeClock) -> tuple[CapacityLedger, CapacityService, Scheduler]:
    """ledger + service + scheduler on ONE FakeClock (the C4 coherence gotcha)."""
    from canopy_server.deps import (
        get_db,
        get_engine,
        get_profile_store,
        get_provider_accounts,
        get_work_store,
    )

    ledger = CapacityLedger(get_db(), now=clock)
    service = CapacityService(get_provider_accounts(), ledger, get_profile_store(),
                              enabled=lambda: True)
    sched = Scheduler(
        get_db(), now=clock, capacity_service=service, capacity_ledger=ledger,
        work_store=get_work_store(), gates=get_engine().gates,
        enabled=lambda: True, resume_jitter_s=0,
    )
    return ledger, service, sched


def _two_orgs(client, make_org, mint_session):
    """Two orgs × one team each, both riding the shared mock pool, with a
    pre-session root assignment (a spawn claimant) apiece."""
    from canopy_server.deps import get_engine

    teams = {}
    for name, org_key, org_name in (
        ("canopy-maintenance", "canopy-inc", "Canopy Inc."),
        ("household", "personal", "Personal"),
    ):
        team = make_org(name=name, seed={"kind": "root", "roleKey": "engineering-lead"})
        org = client.post("/api/orgs", json={"key": org_key, "name": org_name}).json()
        r = client.post(f"/api/teams/{team['id']}/move", json={"organizationId": org["id"]})
        assert r.status_code == 200, r.text
        root = next(a for a in team["agents"] if a["managerId"] is None)
        s = mint_session(team["id"], node_id=root["id"])
        a = get_engine().submit_intent(
            team["id"], s["actuationId"], f"work for {name}", target_node=root["id"]
        ).assignment
        teams[name] = {"team": team, "org": org, "root": root, "session": s,
                       "assignment": a}
    return teams["canopy-maintenance"], teams["household"]


def _seed_steps(db, team_id: str, tokens: int, at: str, tag: str = "") -> None:
    aid = f"as_{team_id}_{tag or at[-6:-1]}"
    with db.transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO work_assignment (id, team_id, actuation_id, intent_id,"
            " node_id, issued_by, state, contract_kind, contract_type, created_at,"
            " updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (aid, team_id, "act_x", "in_x", "a_x", "operator", "closed", "artifact",
             "Doc", at, at),
        )
        conn.execute(
            "INSERT INTO work_step (id, assignment_id, kind, input_tokens, output_tokens,"
            " duration_ms, created_at) VALUES (?,?,?,?,?,?,?)",
            (f"st_{team_id}_{tag or at[-6:-1]}", aid, "production", tokens, 0, 10, at),
        )


def _seed_spend(db, team_id: str, usd: float, at: str, tag: str) -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO ledger_spend_event (id, step_id, team_id, actuation_id, node_id,"
            " task_id, provider, model, input_tokens, output_tokens, cache_read_tokens,"
            " cache_creation_tokens, est_cost_micros, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"sp_{team_id}_{tag}", f"st_{team_id}_{tag}", team_id, "act_x", "a_x",
             None, "mock", "mock-1", 100, 100, 0, 0, int(usd * 1e6), at),
        )


# --------------------------------------------------------------------------- #
# SC-5 — the done-bar: shares honored under contention, on one contended pool
# --------------------------------------------------------------------------- #
def test_sc5_shares_honored_under_contention(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    maint, house = _two_orgs(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")
    ledger, service, sched = _stack(clock)

    # One shared pool, one slot: contention by construction.
    account = service.account_for_session(maint["team"]["id"], maint["root"]["id"])
    assert account is not None
    assert service.account_for_session(house["team"]["id"], house["root"]["id"]).id \
        == account.id  # same mock login — pool truth is shared
    with get_db().transaction() as conn:
        conn.execute("UPDATE provider_account SET max_concurrent_sessions=1 WHERE id=?",
                     (account.id,))
    account = service.accounts.get(account.id)

    # K7: canopy-inc 70 / personal 30.
    for entry, share in ((maint, 70), (house, 30)):
        r = client.put(f"/api/orgs/{entry['org']['id']}/budget",
                       json={"capacityShares": {account.id: share}})
        assert r.status_code == 200, r.text

    # Round 1 — nobody has consumed anything: the bigger share holds the bigger
    # claim, so canopy-inc gets the slot and personal waits.
    first = sched.check(maint["team"]["id"], maint["root"]["id"], maint["assignment"])
    second = sched.check(house["team"]["id"], house["root"]["id"], house["assignment"])
    assert first.admit is True
    assert second.admit is False and second.reason == "share-contention"
    assert second.payload["pool"] == account.id

    # canopy-inc then eats the window: tier-1 delta split entirely onto its team.
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=40.0))
    clock.advance(600)
    _seed_steps(get_db(), maint["team"]["id"], 4000, clock(), tag="r1")
    clock.advance(600)
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=52.0))

    # Round 2 — the idle org accumulated claim while the hungry one consumed:
    # personal's unconsumed 30% now outranks canopy-inc's overdrawn 70%.
    flipped = sched.check(house["team"]["id"], house["root"]["id"], house["assignment"])
    displaced = sched.check(maint["team"]["id"], maint["root"]["id"], maint["assignment"])
    assert flipped.admit is True
    assert displaced.admit is False and displaced.reason == "share-contention"


def test_sc5_reserve_admits_interactive_at_high_utilization(
    client, make_org, mint_session, monkeypatch
):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    maint, house = _two_orgs(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")
    ledger, service, sched = _stack(clock)
    account = service.account_for_session(maint["team"]["id"], maint["root"]["id"])
    with get_db().transaction() as conn:
        conn.execute("UPDATE provider_account SET max_concurrent_sessions=1 WHERE id=?",
                     (account.id,))

    # K8: personal holds 15% of the pool for interactive work; household IS interactive.
    r = client.put(f"/api/orgs/{house['org']['id']}/budget",
                   json={"reserveWatermarkPct": {account.id: 15}})
    assert r.status_code == 200, r.text
    client.put(f"/api/teams/{house['team']['id']}/schedule", json={"priority": "interactive"})

    # The pool runs hot: 86% > the 85% watermark, but NOT exhausted.
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=86.0))

    # Batch holds at the watermark; interactive is admitted against the reserve —
    # capacity pre-provisioned by policy, no emergency knob-turning (04 §5). The
    # batch claimant must not occupy a contention rank it can never win.
    held = sched.check(maint["team"]["id"], maint["root"]["id"], maint["assignment"])
    admitted = sched.check(house["team"]["id"], house["root"]["id"], house["assignment"])
    assert held.admit is False and held.reason == "reserve-watermark"
    assert held.payload["watermarkPct"] == 85.0
    assert admitted.admit is True

    # Below the watermark the reserve does not bind (batch admits again once the
    # pool also has slots — the cap goes back up so only the reserve is in play).
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=60.0))
    with get_db().transaction() as conn:
        conn.execute("UPDATE provider_account SET max_concurrent_sessions=4 WHERE id=?",
                     (account.id,))
    assert sched.check(maint["team"]["id"], maint["root"]["id"],
                       maint["assignment"]).admit is True


def test_priority_breaks_exact_share_ties(client, make_org, mint_session, monkeypatch):
    """04 §6's chain past shares: with no shares configured (equal claims), the
    interactive team's org takes the contended slot — deterministically, never by
    accident of id ordering."""
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    maint, house = _two_orgs(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")
    _ledger, service, sched = _stack(clock)
    account = service.account_for_session(maint["team"]["id"], maint["root"]["id"])
    with get_db().transaction() as conn:
        conn.execute("UPDATE provider_account SET max_concurrent_sessions=1 WHERE id=?",
                     (account.id,))
    client.put(f"/api/teams/{house['team']['id']}/schedule", json={"priority": "interactive"})

    assert sched.check(house["team"]["id"], house["root"]["id"],
                       house["assignment"]).admit is True
    held = sched.check(maint["team"]["id"], maint["root"]["id"], maint["assignment"])
    assert held.admit is False and held.reason == "share-contention"


def test_account_cap_holds_all_spawns_when_full(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    maint, house = _two_orgs(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")
    _ledger, service, sched = _stack(clock)
    account = service.account_for_session(maint["team"]["id"], maint["root"]["id"])
    with get_db().transaction() as conn:
        conn.execute("UPDATE provider_account SET max_concurrent_sessions=1 WHERE id=?",
                     (account.id,))
        # canopy-maintenance already has a live session on the pool.
        conn.execute("UPDATE work_assignment SET state='executing' WHERE id=?",
                     (maint["assignment"].id,))

    hold = sched.check(house["team"]["id"], house["root"]["id"], house["assignment"])
    assert hold.admit is False and hold.reason == "account-session-cap"
    assert hold.payload == {"pool": account.id, "reason": "account-session-cap",
                            "cap": 1, "active": 1, "policy": "hold-resume"}
    # The etiquette cap gates NEW spawns only — the running session is untouched.
    running = sched.check(maint["team"]["id"], maint["root"]["id"],
                          maint["assignment"].model_copy(update={"state": "executing"}))
    assert running.admit is True


# --------------------------------------------------------------------------- #
# The org weekly ceiling (01 §6) — warn, then refuse; never the running work
# --------------------------------------------------------------------------- #
def test_org_ceiling_warns_then_refuses_new_intents(client, make_org, mint_session,
                                                    monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    maint, house = _two_orgs(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")  # a Wednesday; week began Mon 08-10
    _ledger, _service, sched = _stack(clock)
    r = client.put(f"/api/orgs/{maint['org']['id']}/budget",
                   json={"weeklyCostCeilingUsd": 10.0})
    assert r.status_code == 200, r.text

    # Under the warn line: admitted quietly.
    assert sched.admit_intent(maint["team"]["id"]).reason == "ok"

    # 85% of the ceiling, spent this week: admitted with the warning.
    _seed_spend(get_db(), maint["team"]["id"], 8.5, "2026-08-11T09:00:00Z", "w1")
    warned = sched.admit_intent(maint["team"]["id"])
    assert warned.admit is True and warned.reason == "org-budget-approaching"
    assert warned.payload["weekSpendUsd"] == 8.5

    # Crossed: refused, with the week's facts in the payload.
    _seed_spend(get_db(), maint["team"]["id"], 2.0, "2026-08-12T09:00:00Z", "w2")
    refused = sched.admit_intent(maint["team"]["id"])
    assert refused.admit is False and refused.reason == "org-budget"
    assert refused.payload["weekSpendUsd"] == 10.5
    assert refused.payload["weekResetsAt"] == "2026-08-17T00:00:00Z"

    # The ceiling is an admission budget, not a meter: executing work still runs.
    live = sched.check(maint["team"]["id"], maint["root"]["id"],
                       maint["assignment"].model_copy(update={"state": "executing"}))
    assert live.admit is True

    # Isolation (invariant 12): one org's exhaustion never blocks another's admission.
    assert sched.admit_intent(house["team"]["id"]).admit is True

    # Last week's spend is last week's business.
    _seed_spend(get_db(), house["team"]["id"], 500.0, "2026-08-07T09:00:00Z", "old")
    client.put(f"/api/orgs/{house['org']['id']}/budget",
               json={"weeklyCostCeilingUsd": 10.0})
    assert sched.admit_intent(house["team"]["id"]).admit is True


def test_org_ceiling_refuses_at_the_route_with_notification(client, make_org,
                                                            mint_session, monkeypatch):
    """The route wiring: 409 ORG_BUDGET_EXCEEDED + the `attention` notification
    (06 §5 vocabulary). Uses the real clock — spend is stamped `now`, so it lands
    in the current week whichever week that is."""
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from types import SimpleNamespace

    from canopy_server.actuator import Actuator
    from canopy_server.deps import get_db, now_iso

    team = make_org(name="ceilinged", seed={"kind": "root", "roleKey": "engineering-lead"})
    org = client.post("/api/orgs", json={"key": "capped", "name": "Capped"}).json()
    client.post(f"/api/teams/{team['id']}/move", json={"organizationId": org["id"]})
    client.put(f"/api/orgs/{org['id']}/budget", json={"weeklyCostCeilingUsd": 5.0})
    _seed_spend(get_db(), team["id"], 6.0, now_iso(), "rt")

    s = mint_session(team["id"])
    monkeypatch.setattr(
        Actuator, "get_current",
        lambda _self, _tid: SimpleNamespace(state="live", id=s["actuationId"]))
    r = client.post(f"/api/teams/{team['id']}/intents", json={"text": "more work"})
    assert r.status_code == 409, r.text
    body = r.json()["error"]
    assert body["code"] == "ORG_BUDGET_EXCEEDED"
    assert body["budget"]["weekSpendUsd"] == 6.0 and body["budget"]["ceilingUsd"] == 5.0

    notes = client.get(f"/api/teams/{team['id']}/notifications").json()["notifications"]
    (note,) = [n for n in notes if n["kind"] == "capacity-budget"]
    assert note["severity"] == "attention"
    assert "refused" in note["text"]


def test_budget_validation_vectors(client, make_org):
    org = client.post("/api/orgs", json={"key": "val", "name": "Val"}).json()
    for bad in (
        {"weeklyCostCeilingUsd": -1},
        {"weeklyCostCeilingUsd": "lots"},
        {"capacityShares": {"pa_x": -5}},
        {"capacityShares": "everything"},
        {"reserveWatermarkPct": {"pa_x": 150}},
        {"mystery": 1},
    ):
        r = client.put(f"/api/orgs/{org['id']}/budget", json=bad)
        assert r.status_code == 400 and r.json()["error"]["code"] == "BAD_BUDGET", bad
    good = {"weeklyCostCeilingUsd": 40.0, "capacityShares": {"pa_x": 70},
            "reserveWatermarkPct": {"pa_x": 15}}
    r = client.put(f"/api/orgs/{org['id']}/budget", json=good)
    assert r.status_code == 200 and r.json()["budget"] == good
    # The read surface exposes the posture (economics ride GET /orgs/{id}).
    eco = client.get(f"/api/orgs/{org['id']}").json()["economics"]
    assert eco["weeklyCostCeilingUsd"] == 40.0 and eco["weekSpendUsd"] == 0.0


# --------------------------------------------------------------------------- #
# The what-if strip (06 §3) — same math as the chips, nothing auto-applies
# --------------------------------------------------------------------------- #
def test_what_if_enumerates_knobs_from_attribution(client, make_org, mint_session,
                                                   monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    maint, house = _two_orgs(client, make_org, mint_session)
    clock = FakeClock("2026-08-12T12:00:00Z")
    ledger, service, sched = _stack(clock)
    account = service.account_for_session(maint["team"]["id"], maint["root"]["id"])

    # Burn: maintenance 3:1 household over a 12 pp tier-1 delta → 9 and 3 pp/hr-ish.
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=40.0,
        resets_at="2026-08-12T14:00:00Z"))
    clock.advance(600)
    _seed_steps(get_db(), maint["team"]["id"], 3000, clock(), tag="wf")
    _seed_steps(get_db(), house["team"]["id"], 1000, clock(), tag="wf")
    clock.advance(600)
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=52.0,
        resets_at="2026-08-12T14:00:00Z"))

    out = sched.what_if(account.id, needed_pp=6.0)
    assert out["windowKey"] == "mock_window"
    assert out["horizonBasis"] == "until-reset" and out["horizonH"] > 0
    pauses = [s for s in out["suggestions"]
              if len(s["actions"]) == 1 and s["actions"][0]["knob"] == "runState"]
    assert pauses, "pause suggestions must exist for burning teams"
    # The heaviest burner's pause frees the most, and satisfaction is computed
    # against the horizon — server math, zero UI math.
    heavy = max(pauses, key=lambda s: s["freesPpHr"])
    assert heavy["actions"][0]["teamId"] == maint["team"]["id"]
    assert heavy["satisfies"] == (heavy["freesPp"] >= 6.0)
    # A quiet pool yields no suggestions rather than invented ones.
    quiet = sched.what_if(account.id, window_key="never_seen")
    assert quiet["suggestions"] == []


def test_what_if_route_decorates_team_names(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_db

    maint, _house = _two_orgs(client, make_org, mint_session)
    from canopy_server.deps import get_capacity_ledger, get_capacity_service

    service = get_capacity_service()
    ledger = get_capacity_ledger()
    account = service.account_for_session(maint["team"]["id"], maint["root"]["id"])
    # Real-clock burn so the app-wired scheduler sees it too.
    from canopy_server.deps import now_iso

    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=30.0))
    _seed_steps(get_db(), maint["team"]["id"], 2000, now_iso(), tag="rt")
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=39.0))

    r = client.post("/api/capacity/whatif", json={"accountId": account.id})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["windowKey"] == "mock_window"
    assert any(a["teamName"] == "canopy-maintenance"
               for s in out["suggestions"] for a in s["actions"])


# --------------------------------------------------------------------------- #
# The org-filtered aggregate (06 §8): filtered, not falsified
# --------------------------------------------------------------------------- #
def test_capacity_aggregate_org_filter(client, make_org, mint_session, monkeypatch):
    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    from canopy_server.deps import get_capacity_ledger, get_capacity_service, get_db, now_iso

    maint, house = _two_orgs(client, make_org, mint_session)
    service = get_capacity_service()
    ledger = get_capacity_ledger()
    account = service.account_for_session(maint["team"]["id"], maint["root"]["id"])
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=30.0))
    _seed_steps(get_db(), maint["team"]["id"], 3000, now_iso(), tag="agg")
    _seed_steps(get_db(), house["team"]["id"], 1000, now_iso(), tag="agg")
    ledger.record_reading(account.id, WindowReading(
        window_key="mock_window", source="provider-read", utilization_pct=42.0))

    full = client.get("/api/capacity").json()
    acct = next(a for a in full["accounts"] if a["id"] == account.id)
    assert {b["teamId"] for b in acct["burn"]["mock_window"]["teams"]} \
        == {maint["team"]["id"], house["team"]["id"]}
    assert {o["key"] for o in full["organizations"]} >= {"canopy-inc", "personal"}

    filtered = client.get(f"/api/capacity?orgId={house['org']['id']}").json()
    acct_f = next(a for a in filtered["accounts"] if a["id"] == account.id)
    bands = acct_f["burn"]["mock_window"]
    assert [b["teamId"] for b in bands["teams"]] == [house["team"]["id"]]
    # The excluded org's burn stays visible as one labeled band — pool truth.
    assert bands["otherOrgsPpHr"] > 0
    assert [o["key"] for o in filtered["organizations"]] == ["personal"]
