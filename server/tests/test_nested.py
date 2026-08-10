"""Nested child-team handling: recursive validation, export gating, and import re-id."""


def _nested_doc(top, mount_agent_id, child_root_role="team-lead"):
    """Attach a valid single-root child team under `mount_agent_id` of `top`."""
    top = dict(top)
    top["childTeams"] = [
        {
            "mountAgentId": mount_agent_id,
            "team": {
                "kind": "canopy.team",
                "schemaVersion": 2,
                "id": "child-local-id",
                "name": "Support",
                "organizationType": "customer-support-center",
                "agents": [
                    {
                        "id": "c_root",
                        "name": "Support Lead",
                        "role": {"key": child_root_role, "version": 1},
                        "managerId": None,
                        "salary": {
                            "perAssignmentAllowance": 150000,
                            "warnThresholdPct": 80,
                            "hardStop": True,
                        },
                    }
                ],
                "dependencies": [],
                "customRoles": [],
                "childTeams": [],
                "meta": {},
            },
        }
    ]
    return top


def test_nested_export_reids_and_survives_roundtrip(client, make_org):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    nested = _nested_doc(team, team["agents"][0]["id"])
    saved = client.put(f"/api/teams/{team['id']}", json=nested)
    assert saved.status_code == 200, saved.text

    # Export is clean (top root + valid child root); canonical + attachment.
    exported = client.get(f"/api/teams/{team['id']}/export")
    assert exported.status_code == 200, exported.text

    # Re-import assigns fresh ids at every level, including the nested team + its agents.
    result = client.post("/api/teams/import", json=exported.json())
    assert result.status_code == 201
    doc = result.json()["document"]
    assert doc["id"] != team["id"]
    child = doc["childTeams"][0]
    assert child["team"]["id"] != "child-local-id"
    assert child["team"]["agents"][0]["id"] != "c_root"
    # the mount still points at a real top-level agent after re-id
    assert child["mountAgentId"] in {a["id"] for a in doc["agents"]}


def test_nested_child_error_bubbles_with_orgpath(client, make_org):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    nested = _nested_doc(team, team["agents"][0]["id"])
    # Break the child: give it a self-dependency.
    nested["childTeams"][0]["team"]["dependencies"] = [
        {"id": "dz", "from": "c_root", "to": "c_root"}
    ]
    client.put(f"/api/teams/{team['id']}", json=nested)
    issues = client.post(f"/api/teams/{team['id']}/validate?mode=export").json()["issues"]
    codes = {i["code"] for i in issues}
    assert "DEP_SELF" in codes
    assert "CHILD_INVALID" in codes
    # export is blocked by the nested error
    assert client.get(f"/api/teams/{team['id']}/export").status_code == 422
