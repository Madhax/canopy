"""Actuator state machine — readiness, provision→live, deactuate (with a fake sandbox).

The fake sandbox simulates an agent booting by registering itself in the directory on start(), so
the provision/teardown state machine is tested without spawning real processes. The real
subprocess path is covered by test_sandbox.py and end-to-end in the live preview.
"""

from __future__ import annotations

import asyncio

import pytest

from canopy_server.activity import ActivityLog
from canopy_server.actuator import ActuationError, Actuator
from canopy_server.catalog import get_catalog
from canopy_server.db import Db
from canopy_server.directory import AgentDirectory
from canopy_server.ledger import SqliteLedger
from canopy_server.models import Agent, Organization, RoleRef, Salary
from canopy_server.profiles import ProfileStore
from canopy_server.runtokens import RunTokenStore
from canopy_server.sandbox.base import SandboxHandle, SandboxProvider, SandboxSpec, SandboxStatus
from canopy_server.secretstore import LocalEncryptedSecretStore
from canopy_server.sqlite_store import SqliteOrgStore


class FakeSandbox(SandboxProvider):
    key = "fake"

    def __init__(self, directory: AgentDirectory):
        self.directory = directory
        self.stopped: list[str] = []

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        return SandboxHandle(
            id=f"{spec.actuation_id}::{spec.node_id}",
            actuation_id=spec.actuation_id,
            node_id=spec.node_id,
            workspace_root=str(spec.workspace_root),
        )

    async def start(self, handle: SandboxHandle) -> SandboxHandle:
        # Simulate the agent booting and registering its endpoint.
        self.directory.register(
            handle.actuation_id, handle.node_id, "http://127.0.0.1:0",
            {"name": handle.node_id},
        )
        return handle.model_copy(update={"pid": 4242})

    async def stop(self, handle: SandboxHandle, grace_s: int = 10) -> None:
        self.stopped.append(handle.node_id)

    async def destroy(self, handle: SandboxHandle) -> None:
        pass

    async def status(self, handle: SandboxHandle) -> SandboxStatus:
        return SandboxStatus(state="running")

    async def logs(self, handle: SandboxHandle, tail: int = 200) -> str:
        return ""


def _org() -> Organization:
    return Organization(
        id="org-act",
        name="ActTest",
        organizationType="product-engineering",
        updatedAt="2026-07-06T00:00:00Z",
        agents=[
            Agent(id="a_root", name="Lead", role=RoleRef(key="engineering-lead"),
                  managerId=None, salary=Salary(perAssignmentAllowance=100000)),
            Agent(id="a_be", name="Backend", role=RoleRef(key="backend-engineer"),
                  managerId="a_root", salary=Salary(perAssignmentAllowance=100000)),
        ],
    )


def _build(tmp_path):
    db = Db(tmp_path / "canopy.db")
    store = SqliteOrgStore(db)
    profiles = ProfileStore(db)
    secrets = LocalEncryptedSecretStore(db, tmp_path)
    ledger = SqliteLedger(db)
    runtokens = RunTokenStore(db)
    directory = AgentDirectory(db)
    sandbox = FakeSandbox(directory)
    actuator = Actuator(
        db, store, get_catalog(), profiles, secrets, ledger, runtokens, directory, sandbox,
        ActivityLog(db), cp_url="http://127.0.0.1:8700", agent_pythonpath="", boot_timeout_s=5,
        sandboxes_root=tmp_path / "sandboxes",
    )
    return store, profiles, directory, runtokens, sandbox, actuator


def test_readiness_blocks_unbound_nodes(tmp_path):
    store, profiles, *_rest, actuator = _build(tmp_path)
    store.write(_org())
    with pytest.raises(ActuationError) as exc:
        actuator.create_actuation("org-act")
    codes = {i.code for i in exc.value.issues}
    assert "BINDING_MISSING" in codes


def test_provision_to_live_then_deactuate(tmp_path):
    store, profiles, directory, runtokens, sandbox, actuator = _build(tmp_path)
    store.write(_org())
    profile = profiles.create_profile("org-act", name="mock", provider="mock", model="mock-1")
    profiles.set_binding("org-act", "a_root", profile.id)
    profiles.set_binding("org-act", "a_be", profile.id)

    actuation_id = actuator.create_actuation("org-act")
    asyncio.run(actuator.provision(actuation_id))

    view = actuator.get_actuation(actuation_id)
    assert view.state == "live"
    assert {n.nodeId: n.subState for n in view.nodes} == {"a_root": "ready", "a_be": "ready"}
    assert len(directory.list(actuation_id)) == 2

    asyncio.run(actuator.deactuate(actuation_id))
    after = actuator.get_actuation(actuation_id)
    assert after.state == "stopped"
    assert directory.list(actuation_id) == []
    assert set(sandbox.stopped) == {"a_root", "a_be"}


def test_reconciler_restarts_stale_node(tmp_path):
    store, profiles, directory, runtokens, sandbox, actuator = _build(tmp_path)
    store.write(_org())
    profile = profiles.create_profile("org-act", name="mock", provider="mock", model="mock-1")
    profiles.set_binding("org-act", "a_root", profile.id)
    profiles.set_binding("org-act", "a_be", profile.id)
    actuation_id = actuator.create_actuation("org-act")
    asyncio.run(actuator.provision(actuation_id))

    # Simulate a node whose heartbeat went silent (crash) by backdating it far into the past.
    with actuator.db.transaction() as conn:
        conn.execute(
            "UPDATE directory_agent SET last_heartbeat_at='2000-01-01T00:00:00Z' "
            "WHERE actuation_id=? AND node_id='a_be'",
            (actuation_id,),
        )
    asyncio.run(actuator.reconcile_once(actuation_id))

    # The reconciler restarted it: attempts bumped and it re-registered with a fresh heartbeat.
    node = actuator._node(actuation_id, "a_be")
    assert node["attempts"] == 1
    assert "a_be" in sandbox.stopped  # old sandbox was torn down before respawn
    agent = directory.get(actuation_id, "a_be")
    assert agent.lastHeartbeatAt > "2001-01-01T00:00:00Z"  # re-registered, fresh


def test_tokens_all_revoked_after_deactuate(tmp_path):
    store, profiles, directory, runtokens, sandbox, actuator = _build(tmp_path)
    store.write(_org())
    profile = profiles.create_profile("org-act", name="mock", provider="mock", model="mock-1")
    profiles.set_binding("org-act", "a_root", profile.id)
    profiles.set_binding("org-act", "a_be", profile.id)
    actuation_id = actuator.create_actuation("org-act")
    asyncio.run(actuator.provision(actuation_id))
    asyncio.run(actuator.deactuate(actuation_id))
    with actuator.db.connect() as conn:
        rows = conn.execute("SELECT revoked FROM runtoken").fetchall()
    assert rows and all(r["revoked"] == 1 for r in rows)
