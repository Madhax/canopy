"""Organizations, the portfolio home, move-team, and the 410 door (C1).

The Organization entity: flat, budgeted, isolated group of Teams (design/organizations/01).
Never actuated, never a chart; membership is server-side state; the old chart-CRUD paths
answer 410 with the new path in the body.
"""

from __future__ import annotations


def test_default_org_exists_and_lists_teams(client, make_org):
    team = make_org()
    orgs = client.get("/api/orgs").json()
    assert len(orgs) == 1
    default = orgs[0]
    assert default["key"] == "default"
    assert team["id"] in default["teamIds"]


def test_team_summary_carries_membership(client, make_org):
    team = make_org()
    listing = client.get("/api/teams").json()
    (card,) = [c for c in listing if c["id"] == team["id"]]
    default = client.get("/api/orgs").json()[0]
    assert card["organizationId"] == default["id"]
    assert "childTeamCount" in card


def test_org_crud_roundtrip(client):
    r = client.post(
        "/api/orgs",
        json={"key": "canopy-inc", "name": "Canopy Inc.", "purpose": "Serves Canopy.",
              "theme": {"color": "sage"}},
    )
    assert r.status_code == 201, r.text
    org = r.json()
    assert org["key"] == "canopy-inc"

    r = client.put(f"/api/orgs/{org['id']}", json={"name": "Canopy, Inc."})
    assert r.json()["name"] == "Canopy, Inc."

    r = client.put(f"/api/orgs/{org['id']}/budget", json={"weeklyCostCeilingUsd": 40.0})
    assert r.json()["budget"]["weeklyCostCeilingUsd"] == 40.0

    assert client.delete(f"/api/orgs/{org['id']}").status_code == 204
    assert client.get(f"/api/orgs/{org['id']}").status_code == 404


def test_org_key_taken_and_bad_key(client):
    assert client.post("/api/orgs", json={"key": "personal", "name": "P"}).status_code == 201
    r = client.post("/api/orgs", json={"key": "personal", "name": "P2"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORG_KEY_TAKEN"
    r = client.post("/api/orgs", json={"key": "Not A Slug!", "name": "X"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "BAD_ORG_KEY"


def test_delete_blocked_while_teams_present(client, make_org):
    org = client.post("/api/orgs", json={"key": "busy", "name": "Busy"}).json()
    team = make_org()
    r = client.post(f"/api/teams/{team['id']}/move", json={"organizationId": org["id"]})
    assert r.status_code == 200, r.text
    r = client.delete(f"/api/orgs/{org['id']}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORG_NOT_EMPTY"
    # default org can never be deleted
    default = [o for o in client.get("/api/orgs").json() if o["key"] == "default"][0]
    assert client.delete(f"/api/orgs/{default['id']}").status_code in (409,)


def test_move_team_custody_transfer(client, make_org):
    org = client.post("/api/orgs", json={"key": "canopy-inc", "name": "Canopy"}).json()
    team = make_org(name="Docs Pod")
    r = client.post(f"/api/teams/{team['id']}/move", json={"organizationId": org["id"]})
    assert r.status_code == 200
    assert r.json() == {"teamId": team["id"], "organizationId": org["id"]}
    fresh = client.get(f"/api/orgs/{org['id']}").json()
    assert team["id"] in fresh["teamIds"]
    # unknown target org
    r = client.post(f"/api/teams/{team['id']}/move", json={"organizationId": "org_missing1"})
    assert r.status_code == 404


def test_portfolio_aggregate(client, make_org):
    org = client.post("/api/orgs", json={"key": "personal", "name": "Personal"}).json()
    a = make_org(name="Team A")
    b = make_org(name="Team B")
    client.post(f"/api/teams/{b['id']}/move", json={"organizationId": org["id"]})

    portfolio = client.get("/api/portfolio").json()
    by_key = {o["key"]: o for o in portfolio["organizations"]}
    assert set(by_key) == {"default", "personal"}
    assert [t["id"] for t in by_key["default"]["teams"]] == [a["id"]]
    assert [t["id"] for t in by_key["personal"]["teams"]] == [b["id"]]
    card = by_key["default"]["teams"][0]
    assert card["actuation"] is None  # read-only cards carry actuation state (none here)
    assert {"name", "agentCount", "valid"} <= set(card)


def test_old_organization_paths_are_gone(client, make_org):
    team = make_org()
    for path in ("/api/organizations", f"/api/organizations/{team['id']}"):
        r = client.get(path)
        assert r.status_code == 410, path
        err = r.json()["error"]
        assert err["code"] == "MOVED_TO_TEAMS"
        assert err["newPath"].startswith("/api/teams")


def test_v1_document_imports_as_v2(client):
    v1 = {
        "kind": "canopy.organization",
        "schemaVersion": 1,
        "id": "legacy-1",
        "name": "Legacy",
        "organizationType": "product-engineering",
        "agents": [
            {
                "id": "a_root",
                "name": "Lead",
                "role": {"key": "team-lead", "version": 1},
                "managerId": None,
                "salary": {"perAssignmentAllowance": 1000},
            }
        ],
        "dependencies": [],
        "childOrganizations": [],
    }
    r = client.post("/api/teams/import", json=v1)
    assert r.status_code == 201, r.text
    doc = r.json()["document"]
    assert doc["kind"] == "canopy.team"
    assert doc["schemaVersion"] == 2
    assert doc["childTeams"] == []
