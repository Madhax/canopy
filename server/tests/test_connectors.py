"""Connector instances (docs/design/builder-connectors.md): store, resolution precedence,
readiness, the operator routes' secret custody, and repo-source resolution through instances.

Doctrine: the full path runs offline — the GitHub REST dialect is exercised through a stub
client (test_triggers.py) and the git path through local repositories; CI never sees a network.
"""

from __future__ import annotations

import pytest

from canopy_server.catalog import get_catalog


@pytest.fixture()
def team(client, make_org):
    return make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})


def _connector_store():
    from canopy_server.deps import get_connector_store

    return get_connector_store()


def _mk_instance(store, team_id, **kw):
    defaults = dict(
        pack_key="github", name="canopy repo",
        config={"owner": "acme", "repo": "canopy"},
        secret_bindings={"scm-token": "sec_x"},
        enabled_grants=["connector.github.issues.read", "connector.github.repo.read"],
        node_links=None,
    )
    defaults.update(kw)
    return store.create(team_id, defaults.pop("pack_key"), defaults.pop("name"), **defaults)


# ------------------------------------------------------------------ resolution
def test_resolution_scope_mask_and_pin(client, team):
    """The §4 precedence vectors: team-wide serves everyone; a node link scopes; a node pin
    outranks team-wide; the mask excludes; disable kills; [] links nobody."""
    store = _connector_store()
    catalog = get_catalog()
    oid = team["id"]
    node = team["agents"][0]["id"]
    other = team["agents"][1]["id"]

    inst = _mk_instance(store, oid)  # team-wide
    # Direct namespaced key and the provides alias both resolve.
    assert store.resolve(catalog, oid, node, "connector.github.issues.read").instance.id == inst.id
    assert store.resolve(catalog, oid, node, "issues.read").instance.id == inst.id
    assert store.resolve(catalog, oid, node, "repo.read").instance.id == inst.id
    # The mask is a hard gate: pr.create is not enabled on this instance.
    assert store.resolve(catalog, oid, node, "connector.github.pr.create") is None

    # A node-linked second instance outranks the team-wide one FOR THAT NODE only.
    pinned = _mk_instance(store, oid, name="docs repo",
                          config={"owner": "acme", "repo": "docs"}, node_links=[node])
    assert store.resolve(catalog, oid, node, "issues.read").instance.id == pinned.id
    assert store.resolve(catalog, oid, other, "issues.read").instance.id == inst.id

    # Unlinked ([]) is inert; disabled fails closed for everyone.
    store.update(pinned.id, {"nodeLinks": []})
    assert store.resolve(catalog, oid, node, "issues.read").instance.id == inst.id
    store.update(inst.id, {"enabled": False})
    assert store.resolve(catalog, oid, node, "issues.read") is None


def test_readiness_issue_vectors(client, team):
    """CONNECTOR_UNBOUND / CONNECTOR_SECRET_UNBOUND / CONNECTOR_GRANT_DISABLED (§4)."""
    from canopy_server.connectors import readiness_issues

    store = _connector_store()
    catalog = get_catalog()
    oid = team["id"]
    node = team["agents"][0]["id"]
    grants = ["workspace.rw", "connector.github.pr.create"]

    # No instance at all → UNBOUND (abstract keys never trip it — fallback chain by design).
    codes = [c for c, _ in readiness_issues(catalog, store, oid, node, grants)]
    assert codes == ["CONNECTOR_UNBOUND"]
    assert not readiness_issues(catalog, store, oid, node, ["repo.read", "workspace.rw"])

    # Instance exists but the mask excludes the key → GRANT_DISABLED, not UNBOUND.
    inst = _mk_instance(store, oid)
    codes = [c for c, _ in readiness_issues(catalog, store, oid, node, grants)]
    assert codes == ["CONNECTOR_GRANT_DISABLED"]

    # Mask enables it but the credential is missing → SECRET_UNBOUND.
    store.update(inst.id, {"enabledGrants": inst.enabledGrants + ["connector.github.pr.create"],
                           "secretBindings": {}})
    codes = [c for c, _ in readiness_issues(catalog, store, oid, node, grants)]
    assert codes == ["CONNECTOR_SECRET_UNBOUND"]


# ------------------------------------------------------------------ routes
def test_routes_crud_and_secret_custody(client, team):
    """Secrets go in as plaintext, come back as Secret Store ids, and are never readable."""
    oid = team["id"]
    node = team["agents"][0]["id"]

    packs = client.get(f"/api/teams/{oid}/connector-packs").json()["packs"]
    assert {p["key"] for p in packs} == {"github", "local-git"}

    r = client.post(f"/api/teams/{oid}/connectors", json={
        "packKey": "github", "name": "canopy repo",
        "config": {"owner": "acme", "repo": "canopy"},
        "secrets": {"scm-token": "ghp_PLAINTEXT"},
        "enabledGrants": ["connector.github.issues.read"],
        "nodeLinks": [node],
    })
    assert r.status_code == 201, r.text
    inst = r.json()
    sid = inst["secretBindings"]["scm-token"]
    assert sid.startswith("sec_") and "ghp_" not in r.text

    # Re-scope to team-wide via the tri-state linkScope; rotate the secret.
    r = client.put(f"/api/teams/{oid}/connectors/{inst['id']}", json={
        "linkScope": "team", "secrets": {"scm-token": "ghp_ROTATED"},
    })
    assert r.status_code == 200
    assert r.json()["nodeLinks"] is None
    assert "ghp_" not in r.text

    # Validation is loud: unknown pack, foreign grant, unknown node. Incomplete CONFIG is
    # allowed at create (drop → configure → verify); Verify reports it instead.
    bad = [
        {"packKey": "gitlab", "name": "x"},
        {"packKey": "github", "name": "x", "config": {"owner": "a", "repo": "b"},
         "enabledGrants": ["connector.local-git.repo.read"]},
        {"packKey": "github", "name": "x", "config": {"owner": "a", "repo": "b"},
         "nodeLinks": ["a_ghost"]},
    ]
    for body in bad:
        assert client.post(f"/api/teams/{oid}/connectors", json=body).status_code == 400
    dropped = client.post(f"/api/teams/{oid}/connectors", json={
        "packKey": "github", "name": "just dropped", "config": {"branchPattern": "canopy/*"},
    })
    assert dropped.status_code == 201
    v = client.post(
        f"/api/teams/{oid}/connectors/{dropped.json()['id']}/verify"
    ).json()
    assert v["ok"] is False
    assert any(c["name"] == "config:owner" and not c["ok"] for c in v["checks"])

    r = client.delete(f"/api/teams/{oid}/connectors/{inst['id']}")
    assert r.status_code == 204
    remaining = client.get(f"/api/teams/{oid}/connectors").json()["instances"]
    assert [i["name"] for i in remaining] == ["just dropped"]


def test_local_git_instance_binds_the_repo_source(client, team, tmp_path):
    """The step-0 reframe (builder-connectors.md §2): a local-git instance outranks the F8
    binding; deleting it falls back down the chain — no install re-answers anything."""
    from canopy_server.deps import get_repos
    from canopy_server.repos import _git

    oid = team["id"]
    source = tmp_path / "bound-repo"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.email", "op@localhost")
    _git(source, "config", "user.name", "Operator")
    (source / "README.md").write_text("# bound\n", encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-m", "init")

    r = client.post(f"/api/teams/{oid}/connectors", json={
        "packKey": "local-git", "name": "bound repo",
        "config": {"source": str(source)},
        "enabledGrants": ["connector.local-git.repo.read",
                          "connector.local-git.repo.write"],
    })
    assert r.status_code == 201, r.text
    repo = get_repos().ensure_repo(oid)
    assert repo.name == "bound-repo"  # cloned from the instance's source, not the fixture

    # Verify passes for a real repo; fails loud for a broken path.
    iid = r.json()["id"]
    v = client.post(f"/api/teams/{oid}/connectors/{iid}/verify").json()
    assert v["ok"] is True
    client.put(f"/api/teams/{oid}/connectors/{iid}",
               json={"config": {"source": str(tmp_path / "nowhere")}})
    v = client.post(f"/api/teams/{oid}/connectors/{iid}/verify").json()
    assert v["ok"] is False


def test_push_branch_round_trips_to_the_source(client, team, tmp_path):
    """The pr-create executor's first half: a canopy/* branch lands on the team's source
    remote (local path here; the URL form differs only in auth injection)."""
    from canopy_server.deps import get_repos
    from canopy_server.repos import RepoError, _git

    oid = team["id"]
    source = tmp_path / "push-target"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.email", "op@localhost")
    _git(source, "config", "user.name", "Operator")
    (source / "README.md").write_text("# t\n", encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-m", "init")
    _git(source, "config", "receive.denyCurrentBranch", "ignore")

    client.post(f"/api/teams/{oid}/connectors", json={
        "packKey": "local-git", "name": "target",
        "config": {"source": str(source)},
        "enabledGrants": ["connector.local-git.repo.read",
                          "connector.local-git.repo.write"],
    })
    repos = get_repos()
    wt = repos.materialize_worktree(oid, "as_push1")
    from pathlib import Path
    Path(wt["path"], "new.md").write_text("hi\n", encoding="utf-8")
    repos.assemble_pr(oid, "as_push1")  # commits the work
    pushed = repos.push_branch(oid, "canopy/as_push1")
    assert pushed["headSha"] == _git(source, "rev-parse", "canopy/as_push1")

    with pytest.raises(RepoError, match="non-canopy"):
        repos.push_branch(oid, "main")
