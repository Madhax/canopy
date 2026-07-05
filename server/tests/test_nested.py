"""Nested child-organization handling: recursive validation, export gating, and import re-id."""


def _nested_doc(top, mount_agent_id, child_root_role="team-lead"):
    """Attach a valid single-root child org under `mount_agent_id` of `top`."""
    top = dict(top)
    top["childOrganizations"] = [
        {
            "mountAgentId": mount_agent_id,
            "organization": {
                "kind": "canopy.organization",
                "schemaVersion": 1,
                "id": "child-local-id",
                "name": "Support",
                "organizationType": "customer-support-center",
                "agents": [
                    {
                        "id": "c_root",
                        "name": "Support Lead",
                        "role": {"key": child_root_role, "version": 1},
                        "managerId": None,
                        "salary": {"perAssignmentAllowance": 150000, "warnThresholdPct": 80, "hardStop": True},
                    }
                ],
                "dependencies": [],
                "customRoles": [],
                "childOrganizations": [],
                "meta": {},
            },
        }
    ]
    return top


def test_nested_export_reids_and_survives_roundtrip(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    nested = _nested_doc(org, org["agents"][0]["id"])
    saved = client.put(f"/api/organizations/{org['id']}", json=nested)
    assert saved.status_code == 200, saved.text

    # Export is clean (top root + valid child root); canonical + attachment.
    exported = client.get(f"/api/organizations/{org['id']}/export")
    assert exported.status_code == 200, exported.text

    # Re-import assigns fresh ids at every level, including the nested org + its agents.
    result = client.post("/api/organizations/import", json=exported.json())
    assert result.status_code == 201
    doc = result.json()["document"]
    assert doc["id"] != org["id"]
    child = doc["childOrganizations"][0]
    assert child["organization"]["id"] != "child-local-id"
    assert child["organization"]["agents"][0]["id"] != "c_root"
    # the mount still points at a real top-level agent after re-id
    assert child["mountAgentId"] in {a["id"] for a in doc["agents"]}


def test_nested_child_error_bubbles_with_orgpath(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    nested = _nested_doc(org, org["agents"][0]["id"])
    # Break the child: give it a self-dependency.
    nested["childOrganizations"][0]["organization"]["dependencies"] = [
        {"id": "dz", "from": "c_root", "to": "c_root"}
    ]
    client.put(f"/api/organizations/{org['id']}", json=nested)
    issues = client.post(f"/api/organizations/{org['id']}/validate?mode=export").json()["issues"]
    codes = {i["code"] for i in issues}
    assert "DEP_SELF" in codes
    assert "CHILD_INVALID" in codes
    # export is blocked by the nested error
    assert client.get(f"/api/organizations/{org['id']}/export").status_code == 422
