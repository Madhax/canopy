"""Actuator — desired-vs-actual reconciliation for an organization (control-plane.md §2).

Owns the provision/teardown state machine and the reconciler. Provisioning walks the org tree and,
per node, mints an identity + run token, opens a meter from the node's salary, compiles the
charter, creates and starts a sandbox, then waits for the agent to register within a boot timeout.
An organization is "live" only when its whole tree reports ready; teardown revokes tokens, stops
and destroys sandboxes, and closes meters. Actuation is reversible and idempotent — you can tear
down and re-actuate from the same document.

```
requested → validating → provisioning → live
                │              │           │ (node stale) → degraded → (reconcile) → live
                └── failed ◄───┘           │
 live → draining → stopped   (deactuate: revoke tokens, stop + destroy sandboxes, close meters)
```
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .activity import ActivityLog
from .charter import compile_charter
from .db import Db, register_schema
from .deps import now_iso
from .directory import AgentDirectory
from .ids import new_actuation_id
from .ledger import BudgetLedger
from .models import Agent, Catalog, Organization
from .profiles import ProfileStore
from .runtokens import RunTokenStore
from .sandbox.base import SandboxHandle, SandboxProvider, SandboxSpec
from .secretstore import SecretStore
from .validation import validate_organization
from .validation.codes import ValidationIssue, issue

SCHEMA = """
CREATE TABLE IF NOT EXISTS actuation (
    id         TEXT PRIMARY KEY,
    org_id     TEXT NOT NULL,
    state      TEXT NOT NULL,
    error      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_actuation_org ON actuation (org_id);

CREATE TABLE IF NOT EXISTS actuation_node (
    actuation_id        TEXT NOT NULL,
    node_id             TEXT NOT NULL,
    org_path            TEXT NOT NULL DEFAULT '[]',
    sub_state           TEXT NOT NULL DEFAULT 'pending',
    run_token_record_id TEXT,
    meter_id            TEXT,
    charter             TEXT,
    sandbox_handle      TEXT,
    pid                 INTEGER,
    attempts            INTEGER NOT NULL DEFAULT 0,
    error               TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    PRIMARY KEY (actuation_id, node_id)
);
"""
register_schema(SCHEMA)

_ACTIVE_STATES = ("live", "degraded")
_MAX_RESTARTS = 3
_STALE_SECONDS = 30


class ActuationError(Exception):
    """Readiness validation failed; carries the ValidationIssues so the API can 422 them."""

    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("actuation readiness failed")


class ActuationNodeView(BaseModel):
    nodeId: str
    orgPath: list[str]
    subState: str
    status: str | None = None
    endpointUrl: str | None = None
    error: str | None = None


class ActuationView(BaseModel):
    id: str
    orgId: str
    state: str
    error: str | None = None
    createdAt: str
    updatedAt: str
    nodes: list[ActuationNodeView]


def enumerate_nodes(top: Organization) -> Iterator[tuple[list[str], Agent]]:
    """Yield ``(org_path, agent)`` for every agent at every nesting level, roots first per org."""

    def walk(org: Organization, path: list[str]) -> Iterator[tuple[list[str], Agent]]:
        ordered = sorted(org.agents, key=lambda a: (a.managerId is not None, a.id))
        for agent in ordered:
            yield path, agent
        for child in org.childOrganizations:
            yield from walk(child.organization, path + [child.organization.id])

    yield from walk(top, [])


class Actuator:
    def __init__(
        self,
        db: Db,
        store: Any,
        catalog: Catalog,
        profiles: ProfileStore,
        secrets: SecretStore,
        ledger: BudgetLedger,
        runtokens: RunTokenStore,
        directory: AgentDirectory,
        sandbox: SandboxProvider,
        activity: ActivityLog,
        *,
        cp_url: str,
        agent_pythonpath: str,
        boot_timeout_s: int,
        sandboxes_root: Path,
    ):
        self.db = db
        self.store = store
        self.catalog = catalog
        self.profiles = profiles
        self.secrets = secrets
        self.ledger = ledger
        self.runtokens = runtokens
        self.directory = directory
        self.sandbox = sandbox
        self.activity = activity
        self.cp_url = cp_url
        self.agent_pythonpath = agent_pythonpath
        self.boot_timeout_s = boot_timeout_s
        self.sandboxes_root = sandboxes_root

    # -- readiness ---------------------------------------------------------- #
    def check_readiness(self, org: Organization) -> list[ValidationIssue]:
        issues = [
            i for i in validate_organization(org, "export", self.catalog) if i.severity == "error"
        ]
        for org_path, agent in enumerate_nodes(org):
            binding = self.profiles.get_binding_for_node(org.id, agent.id, org_path)
            if binding is None:
                issues.append(issue("BINDING_MISSING", "error", agentIds=[agent.id],
                                    orgPath=org_path))
                continue
            profile = self.profiles.get_profile(binding.profileId)
            if profile is None:
                issues.append(issue("PROFILE_DANGLING", "error", agentIds=[agent.id],
                                    orgPath=org_path))
                continue
            if profile.apiKeySecretId and self.secrets.get_meta(profile.apiKeySecretId) is None:
                issues.append(issue("SECRET_DANGLING", "error", agentIds=[agent.id],
                                    orgPath=org_path))
        return issues

    # -- lifecycle ---------------------------------------------------------- #
    def create_actuation(self, org_id: str) -> str:
        org = self.store.read(org_id)
        issues = self.check_readiness(org)
        if issues:
            raise ActuationError(issues)
        actuation_id = new_actuation_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO actuation (id, org_id, state, created_at, updated_at) "
                "VALUES (?, ?, 'provisioning', ?, ?)",
                (actuation_id, org_id, ts, ts),
            )
        for org_path, agent in enumerate_nodes(org):
            self._insert_node(actuation_id, agent.id, org_path)
        self.activity.log("operator", "actuation.requested", org_id=org_id,
                          subject_ids=[actuation_id])
        return actuation_id

    async def provision(self, actuation_id: str) -> None:
        """Provision every node. Self-contained: runs as a background task, never raises."""
        try:
            row = self._actuation_row(actuation_id)
            if row is None:
                return
            org = self.store.read(row["org_id"])
            for org_path, agent in enumerate_nodes(org):
                try:
                    await self._provision_node(actuation_id, org, org_path, agent)
                except Exception as exc:  # noqa: BLE001 - one node failing must not abort the rest
                    self._set_node(actuation_id, agent.id, sub_state="failed", error=str(exc))
            nodes = self._nodes(actuation_id)
            if nodes and all(n["sub_state"] == "ready" for n in nodes):
                self._set_state(actuation_id, "live")
                self.activity.log("system", "actuation.live", org_id=org.id,
                                  subject_ids=[actuation_id])
            else:
                self._set_state(actuation_id, "degraded")
                self.activity.log("system", "actuation.degraded", org_id=org.id,
                                  subject_ids=[actuation_id])
        except Exception as exc:  # noqa: BLE001 - a background task must never die silently
            self._set_state(actuation_id, "failed", f"provisioning error: {exc}")

    async def _provision_node(
        self, actuation_id: str, top: Organization, org_path: list[str], agent: Agent
    ) -> None:
        self.directory.upsert_provisioning(actuation_id, agent.id)
        binding = self.profiles.get_binding_for_node(top.id, agent.id, org_path)
        profile = self.profiles.get_profile(binding.profileId) if binding else None
        preamble = profile.systemPreamble if profile else ""
        charter = compile_charter(top, org_path, agent.id, catalog=self.catalog,
                                  actuation_id=actuation_id, profile_preamble=preamble)

        meter = self.ledger.open_meter(
            actuation_id, agent.id, agent.salary.perAssignmentAllowance,
            warn_threshold_pct=agent.salary.warnThresholdPct, hard_stop=agent.salary.hardStop,
        )
        token, rec = self.runtokens.issue(
            actuation_id, agent.id, top.id, org_path=org_path, default_meter_id=meter.id
        )
        # Store the charter BEFORE spawning, so the agent can GET /charter the instant it boots.
        self._set_node(
            actuation_id, agent.id, sub_state="booting", run_token_record_id=rec.id,
            meter_id=meter.id, charter=json.dumps(charter.model_dump() if charter else {}),
        )
        workspace_root = self.sandboxes_root / actuation_id / agent.id / "workspace"
        spec = SandboxSpec(
            actuation_id=actuation_id, node_id=agent.id, org_id=top.id,
            workspace_root=workspace_root, env=self._build_env(token, agent.id, actuation_id),
            a2a_port=None,
        )
        handle = await self.sandbox.create(spec)
        handle = await self.sandbox.start(handle)
        self._set_node(
            actuation_id, agent.id,
            sandbox_handle=json.dumps(handle.model_dump()), pid=handle.pid,
        )
        ready = await self._await_ready(actuation_id, agent.id)
        self._set_node(actuation_id, agent.id, sub_state="ready" if ready else "failed",
                       error=None if ready else "boot timeout: agent did not register")

    def _build_env(self, token: str, node_id: str, actuation_id: str) -> dict[str, str]:
        import os

        env = {
            "CANOPY_CP_URL": self.cp_url,
            "CANOPY_RUN_TOKEN": token,
            "CANOPY_NODE_ID": node_id,
            "CANOPY_ACTUATION_ID": actuation_id,
            "CANOPY_A2A_HOST": "127.0.0.1",
            "CANOPY_A2A_PORT": "0",  # bind ephemeral, report endpoint at register
        }
        if self.agent_pythonpath:
            env["PYTHONPATH"] = self.agent_pythonpath
        # Minimal host vars needed for the interpreter to start (Windows needs SystemRoot).
        for key in ("PATH", "SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "PYTHONHOME"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    async def _await_ready(self, actuation_id: str, node_id: str) -> bool:
        deadline = time.monotonic() + self.boot_timeout_s
        while time.monotonic() < deadline:
            agent = self.directory.get(actuation_id, node_id)
            if agent and agent.endpointUrl:
                await self._card_ok(agent.endpointUrl)  # best-effort inbound check
                return True
            await asyncio.sleep(0.25)
        return False

    async def _card_ok(self, endpoint_url: str) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(endpoint_url.rstrip("/") + "/card")
                return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def deactuate(self, actuation_id: str) -> None:
        self._set_state(actuation_id, "draining")
        self.runtokens.revoke_actuation(actuation_id)  # revoke, then stop, then destroy
        for node in self._nodes(actuation_id):
            if node["sandbox_handle"]:
                handle = SandboxHandle(**json.loads(node["sandbox_handle"]))
                try:
                    await self.sandbox.stop(handle)
                    await self.sandbox.destroy(handle)
                except Exception:  # noqa: BLE001
                    pass
            if node["meter_id"]:
                self.ledger.close_meter(node["meter_id"])
        self.directory.remove_actuation(actuation_id)
        self._set_state(actuation_id, "stopped")
        row = self._actuation_row(actuation_id)
        if row:
            self.activity.log("operator", "actuation.stopped", org_id=row["org_id"],
                              subject_ids=[actuation_id])

    # -- reconciler --------------------------------------------------------- #
    async def reconcile_once(self, actuation_id: str) -> None:
        row = self._actuation_row(actuation_id)
        if row is None or row["state"] not in _ACTIVE_STATES:
            return
        threshold = (datetime.now(UTC) - timedelta(seconds=_STALE_SECONDS)).isoformat().replace(
            "+00:00", "Z"
        )
        org = self.store.read(row["org_id"])
        agents_by_id = {a.id: (p, a) for p, a in enumerate_nodes(org)}
        recovered_any = False
        for stale in self.directory.stale(actuation_id, threshold):
            node = self._node(actuation_id, stale.nodeId)
            if node is None or node["attempts"] >= _MAX_RESTARTS:
                continue
            found = agents_by_id.get(stale.nodeId)
            if not found:
                continue
            org_path, agent = found
            self._bump_attempts(actuation_id, stale.nodeId)
            self.activity.log("system", "actuation.node_restart", org_id=org.id,
                              subject_ids=[actuation_id, stale.nodeId])
            await self._restart_node(actuation_id, node)
            await self._provision_node(actuation_id, org, org_path, agent)
            recovered_any = True
        if recovered_any:
            nodes = self._nodes(actuation_id)
            if nodes and all(n["sub_state"] == "ready" for n in nodes):
                self._set_state(actuation_id, "live")

    async def _restart_node(self, actuation_id: str, node: dict) -> None:
        if node["sandbox_handle"]:
            handle = SandboxHandle(**json.loads(node["sandbox_handle"]))
            try:
                await self.sandbox.stop(handle)
                await self.sandbox.destroy(handle)
            except Exception:  # noqa: BLE001
                pass
        if node["run_token_record_id"]:
            self.runtokens.revoke(node["run_token_record_id"])

    def list_active_actuation_ids(self) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM actuation WHERE state IN ('live', 'degraded')"
            ).fetchall()
        return [r["id"] for r in rows]

    # -- views -------------------------------------------------------------- #
    def get_current(self, org_id: str) -> ActuationView | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM actuation WHERE org_id=? AND state NOT IN ('stopped','failed') "
                "ORDER BY created_at DESC LIMIT 1",
                (org_id,),
            ).fetchone()
        if row is None:
            return None
        return self._view(row)

    def get_actuation(self, actuation_id: str) -> ActuationView | None:
        row = self._actuation_row(actuation_id)
        return self._view(row) if row else None

    def get_charter(self, actuation_id: str, node_id: str) -> dict | None:
        node = self._node(actuation_id, node_id)
        if node is None or not node["charter"]:
            return None
        return json.loads(node["charter"])

    def _view(self, row) -> ActuationView:
        nodes: list[ActuationNodeView] = []
        for n in self._nodes(row["id"]):
            d = self.directory.get(row["id"], n["node_id"])
            nodes.append(ActuationNodeView(
                nodeId=n["node_id"], orgPath=json.loads(n["org_path"]), subState=n["sub_state"],
                status=d.status if d else None, endpointUrl=d.endpointUrl if d else None,
                error=n["error"],
            ))
        return ActuationView(
            id=row["id"], orgId=row["org_id"], state=row["state"], error=row["error"],
            createdAt=row["created_at"], updatedAt=row["updated_at"], nodes=nodes,
        )

    # -- row helpers -------------------------------------------------------- #
    def _actuation_row(self, actuation_id: str):
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT * FROM actuation WHERE id=?", (actuation_id,)
            ).fetchone()

    def _set_state(self, actuation_id: str, state: str, error: str | None = None) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE actuation SET state=?, error=?, updated_at=? WHERE id=?",
                (state, error, now_iso(), actuation_id),
            )

    def _insert_node(self, actuation_id: str, node_id: str, org_path: list[str]) -> None:
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO actuation_node (actuation_id, node_id, org_path, "
                "sub_state, created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?)",
                (actuation_id, node_id, json.dumps(org_path), ts, ts),
            )

    def _set_node(self, actuation_id: str, node_id: str, **fields) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [now_iso(), actuation_id, node_id]
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE actuation_node SET {cols}, updated_at=? "  # noqa: S608 - keys are literals
                "WHERE actuation_id=? AND node_id=?",
                values,
            )

    def _bump_attempts(self, actuation_id: str, node_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE actuation_node SET attempts = attempts + 1 WHERE actuation_id=? AND "
                "node_id=?",
                (actuation_id, node_id),
            )

    def _nodes(self, actuation_id: str) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM actuation_node WHERE actuation_id=? ORDER BY node_id",
                (actuation_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _node(self, actuation_id: str, node_id: str) -> dict | None:
        with self.db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM actuation_node WHERE actuation_id=? AND node_id=?",
                (actuation_id, node_id),
            ).fetchone()
        return dict(r) if r else None
