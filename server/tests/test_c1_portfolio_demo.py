"""The C1 done-bar demo (design/organizations/07 §1): two organizations × two teams,
running concurrently on one control plane, with the portfolio legible throughout.

Interleaved loop ticks drive both teams' intents at once — one org's work never touches
the other's (invariant 12): memberships are disjoint, artifacts stay team-scoped, and
each intent completes under its own organization.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))

from canopy_agent.runtime import AgentConfig, loop_tick  # noqa: E402


def _root_of(team: dict) -> dict:
    return next(a for a in team["agents"] if a["managerId"] is None)


def test_two_orgs_two_teams_run_concurrently(client, make_org, mint_session):
    from canopy_server.deps import get_engine
    from canopy_server.main import app

    inc = client.post(
        "/api/orgs", json={"key": "canopy-inc", "name": "Canopy Inc.", "theme": {"color": "sage"}}
    ).json()
    personal = client.post(
        "/api/orgs", json={"key": "personal", "name": "Personal", "theme": {"color": "indigo"}}
    ).json()

    team_a = make_org(name="Canopy Docs", seed={"kind": "root", "roleKey": "engineering-lead"})
    team_b = make_org(name="Household", seed={"kind": "root", "roleKey": "engineering-lead"})
    assert client.post(
        f"/api/teams/{team_a['id']}/move", json={"organizationId": inc["id"]}
    ).status_code == 200
    assert client.post(
        f"/api/teams/{team_b['id']}/move", json={"organizationId": personal["id"]}
    ).status_code == 200

    # Memberships are disjoint — one team never appears behind another org's wall.
    orgs = {o["key"]: o for o in client.get("/api/orgs").json()}
    assert orgs["canopy-inc"]["teamIds"] == [team_a["id"]]
    assert orgs["personal"]["teamIds"] == [team_b["id"]]

    eng = get_engine()
    fleets = {}
    for team in (team_a, team_b):
        root = _root_of(team)
        s = mint_session(team["id"], node_id=root["id"])
        a = eng.submit_intent(
            team["id"], s["actuationId"], f"Draft the weekly report for {team['name']}",
            target_node=root["id"],
        ).assignment
        fleets[team["id"]] = {
            "assignment": a,
            "agent": TestClient(app, headers={"Authorization": f"Bearer {s['token']}"}),
            "cfg": AgentConfig(
                cp_url="http://cp", run_token=s["token"], node_id=root["id"],
                actuation_id=s["actuationId"], a2a_host="127.0.0.1", a2a_port=0,
            ),
        }

    def state(team_id: str) -> str:
        aid = fleets[team_id]["assignment"].id
        return client.get(f"/api/assignments/{aid}").json()["assignment"]["state"]

    # Interleave the two fleets on one control plane — genuinely concurrent operation.
    for _ in range(8):
        for team_id, fleet in fleets.items():
            if state(team_id) != "delivering":
                loop_tick(fleet["agent"], fleet["cfg"])
        if all(state(tid) == "delivering" for tid in fleets):
            break
    assert all(state(tid) == "delivering" for tid in fleets)

    # The portfolio keeps both legible: each team on its own org's card row.
    portfolio = client.get("/api/portfolio").json()
    by_key = {o["key"]: o for o in portfolio["organizations"]}
    assert [t["id"] for t in by_key["canopy-inc"]["teams"]] == [team_a["id"]]
    assert [t["id"] for t in by_key["personal"]["teams"]] == [team_b["id"]]

    # Both intents complete under their own organizations.
    for fleet in fleets.values():
        a = fleet["assignment"]
        client.post(f"/api/assignments/{a.id}/accept", json={"note": "ok"})
        intent = client.get(f"/api/intents/{a.intentId}").json()["intent"]
        assert intent["state"] == "completed"

    # Isolation at the artifact wall: team B's agent cannot read team A's deliverable.
    a_detail = client.get(f"/api/assignments/{fleets[team_a['id']]['assignment'].id}").json()
    ref = a_detail["deliverable"]["artifactRefs"][0]
    foreign = fleets[team_b["id"]]["agent"].get(f"/api/dp/artifacts?ref={ref}")
    assert foreign.status_code == 404  # not even visible across the wall
