"""E3 actuation-readiness checks: GRANT_UNKNOWN, TIER_UNSATISFIABLE (+ the loud waiver), and
CLI_UNAVAILABLE / the runtime override (cli-runtime.md §2, §8)."""

from __future__ import annotations

import pytest

import canopy_server.actuator as actuator_mod


@pytest.fixture()
def pod_actuator(client, make_org, mint_session):
    from canopy_server.deps import get_actuator

    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    # Readiness needs bindings for every node.
    for a in org["agents"]:
        mint_session(org["id"], node_id=a["id"])
    return get_actuator(), org


def _codes(issues) -> set[str]:
    return {i.code for i in issues}


def test_pod_is_ready_under_the_dev_waiver(pod_actuator):
    """The repo canopy.toml waives trusted-local and forces the loop runtime — a keyless dev
    machine still actuates the pod (the mock spine keeps working)."""
    act, org = pod_actuator
    from canopy_server.deps import get_store

    assert act.check_readiness(get_store().read(org["id"])) == []


def test_tier_unsatisfiable_without_the_waiver(pod_actuator, monkeypatch):
    act, org = pod_actuator
    from canopy_server.deps import get_store

    monkeypatch.setattr(actuator_mod, "get_allow_trusted_local", lambda: False)
    issues = act.check_readiness(get_store().read(org["id"]))
    assert "TIER_UNSATISFIABLE" in _codes(issues)
    # The engineer (test.unit.run) and QA (test.run) trip it; the lead holds no execute grants.
    flagged = {aid for i in issues if i.code == "TIER_UNSATISFIABLE" for aid in i.agentIds}
    roles = {a["id"]: a["role"]["key"] for a in org["agents"]}
    assert {roles[a] for a in flagged} == {"backend-engineer", "qa-engineer"}


def test_docs_pod_is_ready_without_the_waiver(client, make_org, mint_session, monkeypatch):
    """E8's posture claim, asserted: docs-only work carries no grant above tier 1, so the
    docs pod actuates on the subprocess tier with allow_trusted_local=False — no waiver
    stretching (mvp.md §4 E8)."""
    from canopy_server.deps import get_actuator, get_store

    org = make_org(seed={"kind": "formation", "formationKey": "docs-pod"})
    for a in org["agents"]:
        mint_session(org["id"], node_id=a["id"])
    act = get_actuator()
    monkeypatch.setattr(actuator_mod, "get_allow_trusted_local", lambda: False)
    issues = act.check_readiness(get_store().read(org["id"]))
    assert "TIER_UNSATISFIABLE" not in _codes(issues)
    assert issues == []
    # And the waiver's loud activity entry has nothing to announce for this org.
    assert act._has_execute_grants(get_store().read(org["id"])) is False


def test_cli_unavailable_when_roles_want_cli_claude(pod_actuator, monkeypatch):
    act, org = pod_actuator
    from canopy_server.deps import get_store

    monkeypatch.setattr(actuator_mod, "get_runtime_override", lambda: "")  # respect the roles
    monkeypatch.setattr(actuator_mod, "_cli_available", lambda: False)
    issues = act.check_readiness(get_store().read(org["id"]))
    assert "CLI_UNAVAILABLE" in _codes(issues)

    monkeypatch.setattr(actuator_mod, "_cli_available", lambda: True)
    issues = act.check_readiness(get_store().read(org["id"]))
    assert "CLI_UNAVAILABLE" not in _codes(issues)


def test_grant_unknown_flags_dangling_role_grants(pod_actuator, monkeypatch):
    act, org = pod_actuator
    from canopy_server.deps import get_store

    broken = act.catalog.model_copy(deep=True)
    be = next(r for r in broken.roles if r.key == "backend-engineer")
    be.toolGrants.append("quantum.entangle")
    monkeypatch.setattr(act, "catalog", broken)
    issues = act.check_readiness(get_store().read(org["id"]))
    assert "GRANT_UNKNOWN" in _codes(issues)


def test_runtime_env_carries_the_kind(pod_actuator):
    act, _org = pod_actuator
    env = act._build_env("tok", "a_x", "act_1", runtime_kind="cli-claude")
    assert env["CANOPY_RUNTIME"] == "cli-claude"
    env2 = act._build_env("tok", "a_x", "act_1")
    assert env2["CANOPY_RUNTIME"] == "loop"


def test_fake_cli_satisfies_the_probe(monkeypatch, tmp_path):
    """The CANOPY_CLI_CMD override makes the probe pass with the shim — CI's readiness path."""
    import json
    import sys
    from pathlib import Path

    fake = Path(__file__).resolve().parent / "fake_claude.py"
    monkeypatch.setenv("CANOPY_CLI_CMD", json.dumps([sys.executable, str(fake)]))
    actuator_mod._cli_available.cache_clear()
    try:
        assert actuator_mod._cli_available() is True
    finally:
        actuator_mod._cli_available.cache_clear()
