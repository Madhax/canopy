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


def test_integrity_catches_dangling_palette():
    catalog = get_catalog()
    broken = catalog.model_copy(deep=True)
    broken.organizationTypes[0].rolePalette.append("no-such-role")
    problems = check_integrity(broken)
    assert any("unknown role" in p for p in problems)
