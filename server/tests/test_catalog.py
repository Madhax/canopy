"""Catalog integrity — unique kebab-case keys, resolvable cross-refs, valid formation wiring."""

from canopy_server.catalog import check_integrity, get_catalog


def test_catalog_loads_clean():
    catalog = get_catalog()
    assert check_integrity(catalog) == []


def test_catalog_shape():
    catalog = get_catalog()
    assert len(catalog.organizationTypes) == 26
    assert len(catalog.roles) == 87
    assert len(catalog.formations) == 16


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
    assert set(grants) == {
        "workspace.rw", "repo.read", "code.repo.write", "test.unit.run", "test.run",
        "repo.merge",
    }
    # Execute-class grants carry the hard tier floor (envelope §3.1); merge is governed.
    assert grants["test.run"].riskClass == "execute" and grants["test.run"].minSandboxTier == 2
    assert "merge" in grants["repo.merge"].governedActions
    assert grants["code.repo.write"].params["branchPattern"] == "canopy/*"

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
