from canopy_server.catalog import get_catalog
from canopy_server.seeds import build_seed, stamp_formation


def test_blank_seed_empty():
    agents, deps = build_seed("product-engineering", {"kind": "blank"})
    assert agents == [] and deps == []


def test_root_seed_single_root():
    agents, deps = build_seed(
        "product-engineering", {"kind": "root", "roleKey": "engineering-lead"}
    )
    assert len(agents) == 1
    assert agents[0].managerId is None
    assert agents[0].role.key == "engineering-lead"
    assert deps == []


def test_root_seed_defaults_to_leadership_role():
    agents, _ = build_seed("product-engineering", {"kind": "root"})
    assert agents[0].role.key == "program-manager"  # first manager in the palette


def test_formation_seed_stamps_pod_with_deps():
    agents, deps = build_seed(
        "product-engineering", {"kind": "formation", "formationKey": "product-engineering-pod"}
    )
    # lead + backend + frontend + qa
    assert len(agents) == 4
    roots = [a for a in agents if a.managerId is None]
    assert len(roots) == 1 and roots[0].role.key == "engineering-lead"
    # QA depends on backend and frontend (two dependency edges)
    assert len(deps) == 2
    # every dependency endpoint is a real agent id, and every member reports to the manager
    agent_ids = {a.id for a in agents}
    for d in deps:
        assert d.from_ in agent_ids and d.to in agent_ids


def test_stamp_formation_reports_to_given_manager():
    catalog = get_catalog()
    agents, _ = stamp_formation(catalog, "sales-pod", manager_manager_id="a_boss")
    manager = [a for a in agents if a.managerId == "a_boss"]
    assert len(manager) == 1 and manager[0].role.key == "sales-director"
