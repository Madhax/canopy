"""Actuation REST edges that don't need real subprocesses (control-plane.md §9)."""

from __future__ import annotations


def test_actuate_blocked_on_readiness(client, make_org):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    r = client.post(f"/api/teams/{team['id']}/actuations")
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "ACTUATION_BLOCKED"
    assert any(i["code"] == "BINDING_MISSING" for i in body["error"]["issues"])


def test_current_is_null_when_not_actuated(client, make_org):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    r = client.get(f"/api/teams/{team['id']}/actuations/current")
    assert r.status_code == 200
    assert r.json() is None


def test_deactuate_404_when_nothing_live(client, make_org):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    r = client.delete(f"/api/teams/{team['id']}/actuations/current")
    assert r.status_code == 404


def test_actuate_unknown_team_404(client):
    r = client.post("/api/teams/nope/actuations")
    assert r.status_code == 404
