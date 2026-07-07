"""Profiles / bindings / secrets operator API (control-plane.md §9)."""

from __future__ import annotations


def test_secrets_are_write_only(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    r = client.post(
        f"/api/organizations/{org['id']}/secrets",
        json={"name": "anthropic", "value": "sk-super-secret"},
    )
    assert r.status_code == 201
    meta = r.json()
    assert meta["name"] == "anthropic"
    assert "value" not in meta and "ciphertext" not in meta  # never returns the key
    listed = client.get(f"/api/organizations/{org['id']}/secrets").json()
    assert listed and all("value" not in s and "ciphertext" not in s for s in listed)


def test_profile_crud_binding_and_validate(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    node = org["agents"][0]["id"]

    p = client.post(
        f"/api/organizations/{org['id']}/profiles",
        json={"name": "mock", "provider": "mock", "model": "mock-1"},
    ).json()
    assert p["id"].startswith("ap_")

    b = client.put(
        f"/api/organizations/{org['id']}/bindings",
        json={"agentNodeId": node, "profileId": p["id"]},
    )
    assert b.status_code == 200
    binds = client.get(f"/api/organizations/{org['id']}/bindings").json()
    assert [x["agentNodeId"] for x in binds] == [node]

    v = client.post(
        f"/api/organizations/{org['id']}/profiles/{p['id']}/validate"
    ).json()
    assert v["ok"] is True  # mock always validates

    up = client.put(
        f"/api/organizations/{org['id']}/profiles/{p['id']}", json={"name": "renamed"}
    ).json()
    assert up["name"] == "renamed"

    assert (
        client.delete(f"/api/organizations/{org['id']}/profiles/{p['id']}").status_code == 204
    )


def test_binding_rejects_dangling_profile(client, make_org):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    r = client.put(
        f"/api/organizations/{org['id']}/bindings",
        json={"agentNodeId": "a_x", "profileId": "ap_does_not_exist"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PROFILE_DANGLING"


def test_profiles_scoped_to_existing_org(client):
    r = client.post(
        "/api/organizations/nope/profiles",
        json={"name": "mock", "provider": "mock", "model": "mock-1"},
    )
    assert r.status_code == 404
