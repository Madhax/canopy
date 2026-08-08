"""Catalog integrity — unique kebab-case keys, resolvable cross-refs, valid formation wiring."""

from canopy_server.catalog import check_integrity, get_catalog


def test_catalog_loads_clean():
    catalog = get_catalog()
    assert check_integrity(catalog) == []


def test_catalog_shape():
    catalog = get_catalog()
    assert len(catalog.organizationTypes) == 26
    assert len(catalog.roles) == 88
    assert len(catalog.formations) == 17


def test_every_palette_role_resolves():
    catalog = get_catalog()
    roles = {r.key for r in catalog.roles}
    for o in catalog.organizationTypes:
        for rk in o.rolePalette:
            assert rk in roles, f"{o.key} palette references unknown role {rk}"


def test_every_formation_slot_and_dep_resolves():
    catalog = get_catalog()
    roles = {r.key for r in catalog.roles}
    for f in catalog.formations:
        slots = {f.manager.slot} | {m.slot for m in f.members}
        assert f.manager.roleKey in roles
        for m in f.members:
            assert m.roleKey in roles
        for d in f.dependencies:
            assert d.from_ in slots and d.to in slots


def test_formation_verify_edges_match_teams_doc():
    """The verify (resolveOn: delivered) edges are exactly the ones docs/teams.md annotates.

    Catches the catalog and the doc drifting apart; parse-level enum enforcement means any
    other value fails before this test runs.
    """
    catalog = get_catalog()
    verify_edges = {
        (f.key, d.from_, d.to)
        for f in catalog.formations
        for d in f.dependencies
        if d.resolveOn == "delivered"
    }
    assert verify_edges == {
        ("product-engineering-pod", "qa", "backend"),
        ("product-engineering-pod", "qa", "frontend"),
        ("docs-pod", "editor", "writer"),
        ("ml-delivery-pod", "qa", "ml"),
        ("newsdesk", "factchecker", "reporter"),
        ("newsdesk", "copyeditor", "reporter"),
        ("build-crew", "inspector", "electrician"),
    }


def test_tool_grants_resolve_and_cover_the_mvp_roles():
    """E3: the minimal toolGrants vocabulary (envelope §3.1) exists, every role reference
    resolves, and the three MVP roles carry exactly the grants mvp.md §1's table needs."""
    catalog = get_catalog()
    grants = {g.key: g for g in catalog.toolGrants}
    # The merged vocabulary (connectors/01 §6): the native base + issues.read + the two v1
    # packs' contributions (github, local-git).
    assert set(grants) == {
        "workspace.rw", "repo.read", "code.repo.write", "docs.repo.write", "test.unit.run",
        "test.run", "repo.merge", "issues.read",
        "connector.github.issues.read", "connector.github.repo.read",
        "connector.github.repo.write", "connector.github.pr.create",
        "connector.local-git.repo.read", "connector.local-git.repo.write",
    }
    # Execute-class grants carry the hard tier floor (envelope §3.1); merge is governed.
    assert grants["test.run"].riskClass == "execute" and grants["test.run"].minSandboxTier == 2
    assert "merge" in grants["repo.merge"].governedActions
    assert grants["code.repo.write"].params["branchPattern"] == "canopy/*"
    # The docs write grant (E8): same executor and branch discipline as code.repo.write, but
    # tier-1 — documentation is never executed downstream, so no hard-wall requirement and
    # no trusted-local waiver for a docs-only pod.
    assert grants["docs.repo.write"].minSandboxTier == 1
    assert grants["docs.repo.write"].executor == "git-mediated"
    assert grants["docs.repo.write"].params["branchPattern"] == "canopy/*"

    roles = {r.key: r for r in catalog.roles}
    assert roles["backend-engineer"].toolGrants == [
        "workspace.rw", "repo.read", "code.repo.write", "test.unit.run",
    ]
    assert roles["qa-engineer"].toolGrants == ["workspace.rw", "repo.read", "test.run"]
    assert roles["engineering-lead"].toolGrants == ["workspace.rw", "repo.read", "repo.merge"]
    for k in ("backend-engineer", "qa-engineer", "engineering-lead"):
        assert roles[k].defaultRuntime == "cli-claude"
    # Non-overlap is enforced the envelope way: the engineer cannot run the full suite,
    # QA cannot write code, the lead can do neither (austerity is the design).
    assert "test.run" not in roles["backend-engineer"].toolGrants
    assert "code.repo.write" not in roles["qa-engineer"].toolGrants
    assert not {"code.repo.write", "test.unit.run", "test.run"} & set(
        roles["engineering-lead"].toolGrants
    )


def test_docs_pod_roles_carry_no_execute_class_grants():
    """E8: the docs pod re-role. The writer writes on a canopy/* branch via the tier-1 docs
    grant, the editor reads, the lead merges — nothing in the pod needs a sandbox tier above
    the subprocess tier, so it actuates with no trusted-local waiver (mvp.md §4 E8)."""
    catalog = get_catalog()
    roles = {r.key: r for r in catalog.roles}
    assert roles["tech-writer"].toolGrants == ["workspace.rw", "repo.read", "docs.repo.write"]
    assert roles["editor"].toolGrants == ["workspace.rw", "repo.read"]
    for k in ("tech-writer", "editor"):
        assert roles[k].defaultRuntime == "cli-claude"

    grants = {g.key: g for g in catalog.toolGrants}
    pod = [(f.manager.roleKey, *[m.roleKey for m in f.members])
           for f in catalog.formations if f.key == "docs-pod"][0]
    assert set(pod) == {"engineering-lead", "tech-writer", "editor"}
    for role_key in pod:
        for gk in roles[role_key].toolGrants:
            assert grants[gk].minSandboxTier < 2, f"{role_key}:{gk} would demand the waiver"


def test_integrity_catches_dangling_tool_grant():
    catalog = get_catalog()
    broken = catalog.model_copy(deep=True)
    broken.roles[0].toolGrants.append("no.such.grant")
    problems = check_integrity(broken)
    assert any("unknown toolGrant" in p for p in problems)


def test_integrity_catches_dangling_palette():
    catalog = get_catalog()
    broken = catalog.model_copy(deep=True)
    broken.organizationTypes[0].rolePalette.append("no-such-role")
    problems = check_integrity(broken)
    assert any("unknown role" in p for p in problems)
