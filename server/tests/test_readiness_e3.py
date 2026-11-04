"""E3 actuation-readiness checks: GRANT_UNKNOWN, TIER_UNSATISFIABLE (+ the loud waiver), and
CLI_UNAVAILABLE / the runtime override (cli-runtime.md §2, §8)."""

from __future__ import annotations

import pytest

import canopy_server.actuator as actuator_mod


@pytest.fixture()
def pod_actuator(client, make_org, mint_session):
    from canopy_server.deps import get_actuator

    team = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    # Readiness needs bindings for every node.
    for a in team["agents"]:
        mint_session(team["id"], node_id=a["id"])
    return get_actuator(), team


def _codes(issues) -> set[str]:
    return {i.code for i in issues}


def test_pod_is_ready_under_the_dev_waiver(pod_actuator):
    """The repo canopy.toml waives trusted-local and forces the loop runtime — a keyless dev
    machine still actuates the pod (the mock spine keeps working)."""
    act, team = pod_actuator
    from canopy_server.deps import get_store

    assert act.check_readiness(get_store().read(team["id"])) == []


def test_tier_unsatisfiable_without_the_waiver(pod_actuator, monkeypatch):
    act, team = pod_actuator
    from canopy_server.deps import get_store

    monkeypatch.setattr(actuator_mod, "get_allow_trusted_local", lambda: False)
    issues = act.check_readiness(get_store().read(team["id"]))
    assert "TIER_UNSATISFIABLE" in _codes(issues)
    # The engineer (test.unit.run) and QA (test.run) trip it; the lead holds no execute grants.
    flagged = {aid for i in issues if i.code == "TIER_UNSATISFIABLE" for aid in i.agentIds}
    roles = {a["id"]: a["role"]["key"] for a in team["agents"]}
    assert {roles[a] for a in flagged} == {"backend-engineer", "qa-engineer"}


def test_docs_pod_is_ready_without_the_waiver(client, make_org, mint_session, monkeypatch):
    """E8's posture claim, asserted: docs-only work carries no grant above tier 1, so the
    docs pod actuates on the subprocess tier with allow_trusted_local=False — no waiver
    stretching (mvp.md §4 E8)."""
    from canopy_server.deps import get_actuator, get_store

    team = make_org(seed={"kind": "formation", "formationKey": "docs-pod"})
    for a in team["agents"]:
        mint_session(team["id"], node_id=a["id"])
    act = get_actuator()
    monkeypatch.setattr(actuator_mod, "get_allow_trusted_local", lambda: False)
    issues = act.check_readiness(get_store().read(team["id"]))
    assert "TIER_UNSATISFIABLE" not in _codes(issues)
    assert issues == []
    # And the waiver's loud activity entry has nothing to announce for this team.
    assert act._has_execute_grants(get_store().read(team["id"])) is False


def test_cli_unavailable_when_roles_want_cli_claude(pod_actuator, monkeypatch):
    act, team = pod_actuator
    from canopy_server.deps import get_store

    monkeypatch.setattr(actuator_mod, "get_runtime_override", lambda: "")  # respect the roles
    monkeypatch.setattr(actuator_mod, "_cli_available", lambda: False)
    issues = act.check_readiness(get_store().read(team["id"]))
    assert "CLI_UNAVAILABLE" in _codes(issues)

    monkeypatch.setattr(actuator_mod, "_cli_available", lambda: True)
    issues = act.check_readiness(get_store().read(team["id"]))
    assert "CLI_UNAVAILABLE" not in _codes(issues)


def test_grant_unknown_flags_dangling_role_grants(pod_actuator, monkeypatch):
    act, team = pod_actuator
    from canopy_server.deps import get_store

    broken = act.catalog.model_copy(deep=True)
    be = next(r for r in broken.roles if r.key == "backend-engineer")
    be.toolGrants.append("quantum.entangle")
    monkeypatch.setattr(act, "catalog", broken)
    issues = act.check_readiness(get_store().read(team["id"]))
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


def test_gemini_profile_routes_cli_role_to_cli_gemini(pod_actuator, monkeypatch):
    """A CLI role bound to a gemini profile selects cli-gemini and probes the Gemini CLI."""
    import json
    import sys
    from pathlib import Path

    from canopy_server.deps import get_profile_store, get_store
    from canopy_server.profiles import ProfileParams

    act, team = pod_actuator
    profiles = get_profile_store()
    gem_prof = profiles.create_profile(
        team["id"], name="Gemini", provider="gemini", model="gemini-2.5-pro",
        api_key_secret_id=None, params=ProfileParams(maxOutputTokens=1024),
    )
    lead = next(a for a in team["agents"] if a["role"]["key"] == "engineering-lead")
    profiles.set_binding(team["id"], lead["id"], gem_prof.id)

    orig_probe = actuator_mod._gemini_cli_available
    monkeypatch.setattr(actuator_mod, "get_runtime_override", lambda: "")
    monkeypatch.setattr(actuator_mod, "_cli_available", lambda: True)
    monkeypatch.setattr(actuator_mod, "_gemini_cli_available", lambda: False)

    team_doc = get_store().read(team["id"])
    lead_agent = next(a for a in team_doc.agents if a.id == lead["id"])
    assert act._node_runtime(team_doc, lead_agent, gem_prof) == "cli-gemini"

    issues = act.check_readiness(team_doc)
    assert "CLI_UNAVAILABLE" in _codes(issues)

    monkeypatch.setattr(actuator_mod, "_gemini_cli_available", orig_probe)
    fake_gemini = Path(__file__).resolve().parent / "fake_gemini.py"
    monkeypatch.setenv("CANOPY_GEMINI_CLI_CMD", json.dumps([sys.executable, str(fake_gemini)]))
    orig_probe.cache_clear()
    try:
        assert orig_probe() is True
        assert "CLI_UNAVAILABLE" not in _codes(act.check_readiness(team_doc))
    finally:
        orig_probe.cache_clear()

    env = act._build_env("tok", lead["id"], "act_1", runtime_kind="cli-gemini",
                         model="gemini-2.5-pro", cli_config_dir="/tmp/gemini-acct-2")
    assert env["CANOPY_RUNTIME"] == "cli-gemini"
    assert env["CANOPY_CLI_MODEL"] == "gemini-2.5-pro"
    assert env["GEMINI_CLI_HOME"] == "/tmp/gemini-acct-2"


def test_any_catalog_role_routes_to_cli_when_bound_to_keyless_profile(
    client, make_org, mint_session, monkeypatch,
):
    """Even a catalog role whose defaultRuntime is 'loop' (e.g. frontend-engineer) routes
    to cli-claude / cli-gemini when bound to a subscription (keyless) anthropic / gemini
    profile, rather than failing in the API gateway for lack of an API key."""
    from canopy_server.deps import get_actuator, get_profile_store, get_store
    from canopy_server.profiles import ProfileParams

    team = make_org(seed={"kind": "root", "roleKey": "frontend-engineer"})
    act = get_actuator()
    profiles = get_profile_store()
    monkeypatch.setattr(actuator_mod, "get_runtime_override", lambda: "")

    claude_sub = profiles.create_profile(
        team["id"], name="Claude Sub", provider="anthropic", model="claude-sonnet-5",
        api_key_secret_id=None, params=ProfileParams(maxOutputTokens=1024),
    )
    gemini_sub = profiles.create_profile(
        team["id"], name="Gemini Sub", provider="gemini", model="gemini-2.5-flash",
        api_key_secret_id=None, params=ProfileParams(maxOutputTokens=1024),
    )
    team_doc = get_store().read(team["id"])
    fe_agent = team_doc.agents[0]
    assert act._node_runtime(team_doc, fe_agent, claude_sub) == "cli-claude"
    assert act._node_runtime(team_doc, fe_agent, gemini_sub) == "cli-gemini"
