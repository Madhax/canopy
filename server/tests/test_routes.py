def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_catalog(client):
    r = client.get("/api/catalog")
    assert r.status_code == 200
    body = r.json()
    assert len(body["organizationTypes"]) == 26
    assert len(body["roles"]) == 87
    assert len(body["formations"]) == 16


def test_create_and_read(client, make_org):
    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    assert org["kind"] == "canopy.organization"
    assert len(org["agents"]) == 4
    r = client.get(f"/api/organizations/{org['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == org["id"]


def test_create_unknown_type_rejected(client):
    r = client.post(
        "/api/organizations",
        json={"name": "X", "organizationType": "not-a-type", "seed": {"kind": "blank"}},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNKNOWN_ORG_TYPE"


def test_list_summaries(client, make_org):
    make_org(seed={"kind": "root", "roleKey": "engineering-lead"}, name="One")
    make_org(seed={"kind": "blank"}, name="Two")
    r = client.get("/api/organizations")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    by_name = {row["name"]: row for row in rows}
    assert by_name["One"]["valid"] is True  # single root, valid
    assert by_name["Two"]["valid"] is False  # blank -> NO_ROOT error
    assert by_name["One"]["agentCount"] == 1


def test_save_persists_with_errors_and_bumps_updatedat(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    org["agents"][0]["salary"]["perAssignmentAllowance"] = 0  # introduce SALARY_INVALID
    r = client.put(f"/api/organizations/{org['id']}", json=org)
    assert r.status_code == 200
    body = r.json()
    assert any(i["code"] == "SALARY_INVALID" for i in body["issues"])
    assert body["document"]["updatedAt"] != org["updatedAt"]
    # persisted despite the error
    again = client.get(f"/api/organizations/{org['id']}").json()
    assert again["agents"][0]["salary"]["perAssignmentAllowance"] == 0


def test_stale_write_conflict(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    first = client.put(f"/api/organizations/{org['id']}", json=org)
    assert first.status_code == 200
    # org still carries the OLD updatedAt -> conflict
    second = client.put(f"/api/organizations/{org['id']}", json=org)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "STALE_WRITE"


def test_immutable_fields_reimposed(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    original_created = org["createdAt"]
    org["createdAt"] = "1999-01-01T00:00:00Z"  # attempt to change immutable field
    r = client.put(f"/api/organizations/{org['id']}", json=org)
    assert r.status_code == 200
    assert r.json()["document"]["createdAt"] == original_created


def test_id_mismatch_rejected(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    org["id"] = "different"
    r = client.put("/api/organizations/different", json=org)
    assert r.status_code == 404  # no such stored doc under the mismatched url


def test_delete(client, make_org):
    org = make_org()
    assert client.delete(f"/api/organizations/{org['id']}").status_code == 204
    assert client.get(f"/api/organizations/{org['id']}").status_code == 404


def test_validate_modes(client, make_org):
    org = make_org(seed={"kind": "blank"})
    draft = client.post(f"/api/organizations/{org['id']}/validate?mode=draft").json()["issues"]
    export = client.post(f"/api/organizations/{org['id']}/validate?mode=export").json()["issues"]
    # NO_ROOT is a warning in draft, an error in export
    assert any(i["code"] == "NO_ROOT" and i["severity"] == "warning" for i in draft)
    assert any(i["code"] == "NO_ROOT" and i["severity"] == "error" for i in export)


def test_export_gates_on_errors(client, make_org):
    blank = make_org(seed={"kind": "blank"})
    r = client.get(f"/api/organizations/{blank['id']}/export")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "EXPORT_BLOCKED"


def test_export_success_is_canonical(client, make_org):
    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    r = client.get(f"/api/organizations/{org['id']}/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    body = r.json()
    ids = [a["id"] for a in body["agents"]]
    assert ids == sorted(ids)  # agents sorted by id in canonical export


def test_import_reassigns_all_ids(client, make_org):
    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    r = client.post("/api/organizations/import", json=org)
    assert r.status_code == 201
    imported = r.json()["document"]
    assert imported["id"] != org["id"]
    old_agent_ids = {a["id"] for a in org["agents"]}
    new_agent_ids = {a["id"] for a in imported["agents"]}
    assert old_agent_ids.isdisjoint(new_agent_ids)
    assert len(imported["agents"]) == len(org["agents"])
    assert len([a for a in imported["agents"] if a["managerId"] is None]) == 1


def test_import_rejects_bad_schema(client):
    r = client.post("/api/organizations/import", json={"kind": "canopy.organization", "nope": 1})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "SCHEMA_INVALID"
