"""E7 — cadences (engine.md §4): the cron matcher, the CRUD API, and the scheduler's fire /
skip / coalesce semantics. The scheduler is driven directly with injected `now` values (the 30 s
lifespan loop just calls `run_once()`); use-case #30's daily standup is the acceptance shape."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from canopy_server.engine.cadence import (
    CronError,
    next_fire,
    parse_cron,
    validate_cron,
)


def _seed_live_actuation(actuation_id: str, org_id: str) -> None:
    from canopy_server.deps import get_db, now_iso

    ts = now_iso()
    with get_db().transaction() as conn:
        conn.execute(
            "INSERT INTO actuation (id, org_id, state, created_at, updated_at) VALUES (?,?,?,?,?)",
            (actuation_id, org_id, "live", ts, ts),
        )


def _root_of(org: dict) -> dict:
    return next(a for a in org["agents"] if a["managerId"] is None)


# --------------------------------------------------------------------------- #
# Cron matcher
# --------------------------------------------------------------------------- #
def test_cron_parses_fields():
    c = parse_cron("*/15 9-17 * * 1-5")
    assert c.minutes == frozenset({0, 15, 30, 45})
    assert c.hours == frozenset(range(9, 18))
    assert c.doms == frozenset(range(1, 32)) and c.dom_star
    assert c.dows == frozenset({1, 2, 3, 4, 5}) and not c.dow_star


def test_cron_sunday_is_zero_and_seven():
    assert parse_cron("0 0 * * 7").dows == parse_cron("0 0 * * 0").dows == frozenset({0})


def test_cron_lists_and_bare_value_with_step():
    c = parse_cron("5,35 3/4 * * *")
    assert c.minutes == frozenset({5, 35})
    assert c.hours == frozenset({3, 7, 11, 15, 19, 23})  # Vixie: "3/4" = from 3 to top by 4


@pytest.mark.parametrize("expr", [
    "* * * *",            # 4 fields
    "60 * * * *",         # minute out of range
    "* 24 * * *",         # hour out of range
    "* * 0 * *",          # day-of-month floor is 1
    "* * * 13 *",         # month out of range
    "5-1 * * * *",        # inverted range
    "* * * * mon",        # names unsupported
    "*/0 * * * *",        # zero step
])
def test_cron_rejects_malformed(expr):
    with pytest.raises(CronError):
        parse_cron(expr)


def test_cron_unsatisfiable_rejected_by_validate():
    # Parses fine, but Feb 31 never exists — validate_cron proves it never fires.
    assert next_fire(parse_cron("0 0 31 2 *"), datetime(2026, 1, 1, tzinfo=UTC)) is None
    with pytest.raises(CronError):
        validate_cron("0 0 31 2 *")


def test_next_fire_is_strictly_after():
    c = parse_cron("30 12 * * *")
    at = datetime(2026, 8, 3, 12, 30, tzinfo=UTC)
    assert next_fire(c, at) == datetime(2026, 8, 4, 12, 30, tzinfo=UTC)
    just_before = datetime(2026, 8, 3, 12, 29, tzinfo=UTC)
    assert next_fire(c, just_before) == at


def test_next_fire_picks_first_slot_same_day():
    c = parse_cron("*/20 9,14 * * *")
    assert next_fire(c, datetime(2026, 8, 3, 9, 21, tzinfo=UTC)) == datetime(
        2026, 8, 3, 9, 40, tzinfo=UTC
    )
    assert next_fire(c, datetime(2026, 8, 3, 10, 0, tzinfo=UTC)) == datetime(
        2026, 8, 3, 14, 0, tzinfo=UTC
    )


def test_next_fire_vixie_or_rule():
    # Both day fields restricted: 2026-08-01 is a Saturday; 2026-08-03 is the first Monday.
    c = parse_cron("0 0 1 * 1")
    start = datetime(2026, 7, 31, tzinfo=UTC)
    first = next_fire(c, start)
    assert first == datetime(2026, 8, 1, tzinfo=UTC)  # day-of-month arm
    assert next_fire(c, first) == datetime(2026, 8, 3, tzinfo=UTC)  # day-of-week arm
    # dom is a star: ONLY the weekday restricts.
    monday_only = parse_cron("0 0 * * 1")
    assert next_fire(monday_only, start) == datetime(2026, 8, 3, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# CRUD API
# --------------------------------------------------------------------------- #
def test_cadence_crud_over_http(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)

    r = client.post(f"/api/organizations/{org['id']}/cadences", json={
        "name": "daily standup", "cron": "0 9 * * 1-5",
        "intentText": "Report status of all current work", "nodeId": root["id"],
    })
    assert r.status_code == 201, r.text
    cadence = r.json()
    assert cadence["enabled"] and cadence["lastFiredAt"] is None
    assert cadence["nextFireAt"] is not None  # computed for the management list

    lst = client.get(f"/api/organizations/{org['id']}/cadences").json()["cadences"]
    assert [c["id"] for c in lst] == [cadence["id"]]

    upd = client.put(
        f"/api/organizations/{org['id']}/cadences/{cadence['id']}", json={"enabled": False}
    )
    assert upd.status_code == 200
    assert upd.json()["enabled"] is False and upd.json()["nextFireAt"] is None

    assert client.delete(
        f"/api/organizations/{org['id']}/cadences/{cadence['id']}"
    ).status_code == 204
    assert client.get(f"/api/organizations/{org['id']}/cadences").json()["cadences"] == []


def test_cadence_create_validates(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    url = f"/api/organizations/{org['id']}/cadences"

    bad_cron = client.post(url, json={"name": "x", "cron": "not cron", "intentText": "y"})
    assert bad_cron.status_code == 422 and bad_cron.json()["error"]["code"] == "BAD_CRON"

    never = client.post(url, json={"name": "x", "cron": "0 0 31 2 *", "intentText": "y"})
    assert never.status_code == 422 and never.json()["error"]["code"] == "BAD_CRON"

    bad_node = client.post(url, json={
        "name": "x", "cron": "0 9 * * *", "intentText": "y", "nodeId": "a_ghost",
    })
    assert bad_node.status_code == 422 and bad_node.json()["error"]["code"] == "BAD_NODE"

    blank = client.post(url, json={"name": " ", "cron": "0 9 * * *", "intentText": "y"})
    assert blank.status_code == 422 and blank.json()["error"]["code"] == "BAD_CADENCE"

    assert client.post("/api/organizations/nope/cadences", json={
        "name": "x", "cron": "0 9 * * *", "intentText": "y",
    }).status_code == 404
    # Updating/deleting through the wrong org 404s (ownership check).
    other = make_org(name="Other")
    ok = client.post(url, json={"name": "x", "cron": "0 9 * * *", "intentText": "y"}).json()
    assert client.put(
        f"/api/organizations/{other['id']}/cadences/{ok['id']}", json={"enabled": False}
    ).status_code == 404
    assert client.delete(
        f"/api/organizations/{other['id']}/cadences/{ok['id']}"
    ).status_code == 404


# --------------------------------------------------------------------------- #
# Scheduler semantics (engine.md §4): fire, misfire=skip, coalesce, provenance.
# --------------------------------------------------------------------------- #
def _standup(client, org, root, cron="0 9 * * *"):
    r = client.post(f"/api/organizations/{org['id']}/cadences", json={
        "name": "daily standup", "cron": cron,
        "intentText": "Report status of all current work as a StatusReport",
        "nodeId": root["id"],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _activity_kinds(org_id: str) -> list[str]:
    from canopy_server.deps import get_activity

    return [row["kind"] for row in get_activity().list(org_id, after_seq=0, limit=500)]


def test_cadence_fires_an_ordinary_intent(client, make_org, mint_session):
    from canopy_server.deps import get_cadence_scheduler, get_work_store

    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])
    cadence = _standup(client, org, root)

    # The next 09:00 after creation is at most 24h out — two days out it is overdue.
    now = datetime.now(UTC) + timedelta(days=2)
    fired = get_cadence_scheduler().run_once(now)
    assert [i.cadenceId for i in fired] == [cadence["id"]]

    # From here it is indistinguishable from operator work: a funded root assignment on the
    # lead, gates owned by the operator — provenance rides createdBy + cadenceId.
    intent = fired[0]
    assert intent.createdBy == "cadence" and intent.targetNode == root["id"]
    a = get_work_store().get_assignment(intent.rootAssignmentId)
    assert a.state == "briefed" and a.issuedBy == "operator" and a.meterId is not None

    listed = client.get(f"/api/organizations/{org['id']}/intents").json()["intents"]
    assert [i["cadenceId"] for i in listed] == [cadence["id"]]
    notif = client.get(f"/api/organizations/{org['id']}/notifications").json()["notifications"]
    assert [n["kind"] for n in notif if n["kind"] == "cadence-fired"] == ["cadence-fired"]
    assert "cadence.fired" in _activity_kinds(org["id"])

    # Same pass again: the occurrence was consumed (last_fired_at advanced) — nothing new.
    assert get_cadence_scheduler().run_once(now) == []
    row = client.get(f"/api/organizations/{org['id']}/cadences").json()["cadences"][0]
    assert row["lastFiredAt"] is not None


def test_cadence_misfire_skips_while_previous_open(client, make_org, mint_session):
    from canopy_server.deps import get_cadence_scheduler, get_engine, get_work_store

    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])
    _standup(client, org, root)

    scheduler = get_cadence_scheduler()
    first = scheduler.run_once(datetime.now(UTC) + timedelta(days=2))
    assert len(first) == 1

    # Next day's occurrence, previous intent still open → skipped AND consumed.
    assert scheduler.run_once(datetime.now(UTC) + timedelta(days=3)) == []
    assert "cadence.skipped" in _activity_kinds(org["id"])
    intents = get_work_store().list_intents(org["id"])
    assert len(intents) == 1

    # Close it (cancel cascades from the root assignment) → the day after fires again.
    get_engine().cancel_assignment(first[0].rootAssignmentId)
    again = scheduler.run_once(datetime.now(UTC) + timedelta(days=4))
    assert len(again) == 1 and again[0].cadenceId == first[0].cadenceId


def test_cadence_missed_occurrences_coalesce(client, make_org, mint_session):
    """Downtime does not backfill: N missed occurrences collapse into one fire."""
    from canopy_server.deps import get_cadence_scheduler, get_work_store

    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])
    _standup(client, org, root)

    # Ten days of "downtime" since creation → exactly one intent, not ten.
    fired = get_cadence_scheduler().run_once(datetime.now(UTC) + timedelta(days=10))
    assert len(fired) == 1
    assert len(get_work_store().list_intents(org["id"])) == 1


def test_cadence_disabled_or_unactuated_never_fires(client, make_org, mint_session):
    from canopy_server.deps import get_cadence_scheduler, get_work_store

    # Not actuated: the occurrence is consumed and the skip logged — no intent, no crash.
    cold = make_org(name="Cold", seed={"kind": "root", "roleKey": "engineering-lead"})
    cold_root = _root_of(cold)
    _standup(client, cold, cold_root)
    assert get_cadence_scheduler().run_once(datetime.now(UTC) + timedelta(days=2)) == []
    assert get_work_store().list_intents(cold["id"]) == []
    assert "cadence.skipped" in _activity_kinds(cold["id"])
    row = client.get(f"/api/organizations/{cold['id']}/cadences").json()["cadences"][0]
    assert row["lastFiredAt"] is not None  # consumed, not deferred

    # Disabled: not even consumed — the schedule is simply off.
    org = make_org(name="Warm", seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])
    cadence = _standup(client, org, root)
    client.put(f"/api/organizations/{org['id']}/cadences/{cadence['id']}",
               json={"enabled": False})
    assert get_cadence_scheduler().run_once(datetime.now(UTC) + timedelta(days=30)) == []
    assert get_work_store().list_intents(org["id"]) == []
