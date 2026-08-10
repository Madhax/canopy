"""Actuator — desired-vs-actual reconciliation for an team (control-plane.md §2).

Owns the provision/teardown state machine and the reconciler. Provisioning walks the team tree and,
per node, mints an identity + run token, opens a meter from the node's salary, compiles the
charter, creates and starts a sandbox, then waits for the agent to register within a boot timeout.
An team is "live" only when its whole tree reports ready; teardown revokes tokens, stops
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
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .activity import ActivityLog
from .charter import compile_charter
from .config import get_allow_trusted_local, get_runtime_override
from .db import Db, register_schema
from .deps import now_iso
from .directory import AgentDirectory
from .ids import new_actuation_id
from .ledger import BudgetLedger
from .models import Agent, Catalog, Team
from .profiles import ProfileStore
from .router import MessageRouter
from .runtokens import RunTokenStore
from .sandbox.base import SandboxHandle, SandboxProvider, SandboxSpec
from .secretstore import SecretStore
from .store import StoreError
from .validation import validate_team
from .validation.codes import ValidationIssue, issue

SCHEMA = """
CREATE TABLE IF NOT EXISTS actuation (
    id         TEXT PRIMARY KEY,
    team_id     TEXT NOT NULL,
    state      TEXT NOT NULL,
    error      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_actuation_org ON actuation (team_id);

CREATE TABLE IF NOT EXISTS actuation_node (
    actuation_id        TEXT NOT NULL,
    node_id             TEXT NOT NULL,
    team_path            TEXT NOT NULL DEFAULT '[]',
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
    teamPath: list[str]
    subState: str
    status: str | None = None
    endpointUrl: str | None = None
    error: str | None = None


class ActuationView(BaseModel):
    id: str
    teamId: str
    state: str
    error: str | None = None
    createdAt: str
    updatedAt: str
    nodes: list[ActuationNodeView]


@lru_cache(maxsize=1)
def _cli_available() -> bool:
    """One probe per process (cli-runtime.md §2's PROFILE_UNREACHABLE analogue): is a working
    `claude` (or the CANOPY_CLI_CMD override — the fake-CLI shim in CI) answering --version?"""
    import shutil
    import subprocess

    raw = os.environ.get("CANOPY_CLI_CMD", "claude")
    cmd = json.loads(raw) if raw.strip().startswith("[") else [raw]
    # Windows: CreateProcess never applies PATHEXT to a bare name, so resolve the npm
    # shim (claude.cmd) to its real path before spawning — bare "claude" is WinError 2.
    resolved = shutil.which(cmd[0])
    if resolved:
        cmd[0] = resolved
    elif not Path(cmd[0]).exists():
        return False
    try:
        r = subprocess.run([*cmd, "--version"], capture_output=True, timeout=15, check=False)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def enumerate_nodes(top: Team) -> Iterator[tuple[list[str], Agent]]:
    """Yield ``(team_path, agent)`` for every agent at every nesting level, roots first per team."""

    def walk(team: Team, path: list[str]) -> Iterator[tuple[list[str], Agent]]:
        ordered = sorted(team.agents, key=lambda a: (a.managerId is not None, a.id))
        for agent in ordered:
            yield path, agent
        for child in team.childTeams:
            yield from walk(child.team, path + [child.team.id])

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
        work_root: Path | None = None,
        router: MessageRouter | None = None,
        home_resolver=None,
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
        # F13/F16: the actuation-INDEPENDENT home for assignment work and logs — the position
        # owns its conversations and audit trail, the way it already owns work/meters/memory.
        self.work_root = work_root if work_root is not None else sandboxes_root.parent / "work"
        # C1 filesystem regrouping (07 §2.5): when set, a node's work home is
        # <team-home>/work/<node> instead of <work_root>/<team>/<node>.
        self.home_resolver = home_resolver
        self.router = router

    # -- readiness ---------------------------------------------------------- #
    def _role_for(self, team: Team, agent: Agent):
        role = None
        if self.catalog:
            role = next((r for r in self.catalog.roles if r.key == agent.role.key), None)
        return role or next((r for r in team.customRoles if r.key == agent.role.key), None)

    def _node_runtime(self, team: Team, agent: Agent) -> str:
        override = get_runtime_override()
        if override:
            return override
        role = self._role_for(team, agent)
        return getattr(role, "defaultRuntime", "loop") or "loop"

    def _has_execute_grants(self, team: Team) -> bool:
        grants = {g.key: g for g in (self.catalog.toolGrants if self.catalog else [])}
        for _path, agent in enumerate_nodes(team):
            role = self._role_for(team, agent)
            for gk in getattr(role, "toolGrants", []) or []:
                g = grants.get(gk)
                if g is not None and g.minSandboxTier >= 2:
                    return True
        return False

    def check_readiness(self, team: Team) -> list[ValidationIssue]:
        issues = [
            i for i in validate_team(team, "export", self.catalog) if i.severity == "error"
        ]
        grant_keys = {g.key: g for g in (self.catalog.toolGrants if self.catalog else [])}
        from .connectors import ConnectorStore
        from .connectors import readiness_issues as connector_readiness

        conn_store = ConnectorStore(self.db)
        needs_cli = False
        for team_path, agent in enumerate_nodes(team):
            role = self._role_for(team, agent)
            role_grants = list(getattr(role, "toolGrants", []) or [])
            for gk in role_grants:
                grant = grant_keys.get(gk)
                if grant is None:
                    issues.append(issue("GRANT_UNKNOWN", "error", agentIds=[agent.id],
                                        teamPath=team_path))
                elif grant.minSandboxTier >= 2 and not get_allow_trusted_local():
                    # The subprocess provider is the trusted-local tier; execute-class grants
                    # need a hard wall (envelope §3.1) unless the operator waives it loudly
                    # (cli-runtime.md §8).
                    issues.append(issue("TIER_UNSATISFIABLE", "error", agentIds=[agent.id],
                                        teamPath=team_path))
            if self.catalog is not None:
                # Connector readiness (builder-connectors.md §4): namespaced connector grants
                # must resolve to an instance in this node's reach, credentials bound.
                for code, _detail in connector_readiness(
                    self.catalog, conn_store, team.id, agent.id, role_grants
                ):
                    issues.append(issue(code, "error", agentIds=[agent.id],
                                        teamPath=team_path))
            if self._node_runtime(team, agent) == "cli-claude":
                needs_cli = True
            binding = self.profiles.get_binding_for_node(team.id, agent.id, team_path)
            if binding is None:
                issues.append(issue("BINDING_MISSING", "error", agentIds=[agent.id],
                                    teamPath=team_path))
                continue
            profile = self.profiles.get_profile(binding.profileId)
            if profile is None:
                issues.append(issue("PROFILE_DANGLING", "error", agentIds=[agent.id],
                                    teamPath=team_path))
                continue
            if profile.apiKeySecretId and self.secrets.get_meta(profile.apiKeySecretId) is None:
                issues.append(issue("SECRET_DANGLING", "error", agentIds=[agent.id],
                                    teamPath=team_path))
        if needs_cli and not _cli_available():
            issues.append(issue("CLI_UNAVAILABLE", "error"))
        return issues

    # -- lifecycle ---------------------------------------------------------- #
    def create_actuation(self, team_id: str) -> str:
        team = self.store.read(team_id)
        issues = self.check_readiness(team)
        if issues:
            raise ActuationError(issues)
        actuation_id = new_actuation_id()
        # The trusted-local waiver is loud, once, logged (cli-runtime.md §8).
        if get_allow_trusted_local() and self._has_execute_grants(team):
            self.activity.log(
                "operator", "execution.trusted-local-waiver", team_id=team_id,
                subject_ids=[actuation_id],
                payload={"note": "execute-class grants running on the subprocess tier by "
                                 "explicit canopy.toml waiver (execution.allow_trusted_local)"},
            )
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO actuation (id, team_id, state, created_at, updated_at) "
                "VALUES (?, ?, 'provisioning', ?, ?)",
                (actuation_id, team_id, ts, ts),
            )
        for team_path, agent in enumerate_nodes(team):
            self._insert_node(actuation_id, agent.id, team_path)
        if self.router is not None:
            self.router.derive_channels(actuation_id, team)  # chart → allowed channels (A3)
        self.activity.log("operator", "actuation.requested", team_id=team_id,
                          subject_ids=[actuation_id])
        return actuation_id

    async def provision(self, actuation_id: str) -> None:
        """Provision every node. Self-contained: runs as a background task, never raises."""
        try:
            row = self._actuation_row(actuation_id)
            if row is None:
                return
            team = self.store.read(row["team_id"])
            for team_path, agent in enumerate_nodes(team):
                try:
                    await self._provision_node(actuation_id, team, team_path, agent)
                except Exception as exc:  # noqa: BLE001 - one node failing must not abort the rest
                    self._set_node(actuation_id, agent.id, sub_state="failed", error=str(exc))
            nodes = self._nodes(actuation_id)
            if nodes and all(n["sub_state"] == "ready" for n in nodes):
                self._set_state(actuation_id, "live")
                self.activity.log("system", "actuation.live", team_id=team.id,
                                  subject_ids=[actuation_id])
            else:
                self._set_state(actuation_id, "degraded")
                self.activity.log("system", "actuation.degraded", team_id=team.id,
                                  subject_ids=[actuation_id])
        except Exception as exc:  # noqa: BLE001 - a background task must never die silently
            self._set_state(actuation_id, "failed", f"provisioning error: {exc}")

    async def _provision_node(
        self, actuation_id: str, top: Team, team_path: list[str], agent: Agent
    ) -> None:
        self.directory.upsert_provisioning(actuation_id, agent.id)
        binding = self.profiles.get_binding_for_node(top.id, agent.id, team_path)
        profile = self.profiles.get_profile(binding.profileId) if binding else None
        preamble = profile.systemPreamble if profile else ""
        charter = compile_charter(top, team_path, agent.id, catalog=self.catalog,
                                  actuation_id=actuation_id, profile_preamble=preamble)

        meter = self.ledger.open_meter(
            actuation_id, agent.id, agent.salary.perAssignmentAllowance,
            warn_threshold_pct=agent.salary.warnThresholdPct, hard_stop=agent.salary.hardStop,
        )
        token, rec = self.runtokens.issue(
            actuation_id, agent.id, top.id, team_path=team_path, default_meter_id=meter.id
        )
        # Store the charter BEFORE spawning, so the agent can GET /charter the instant it boots.
        self._set_node(
            actuation_id, agent.id, sub_state="booting", run_token_record_id=rec.id,
            meter_id=meter.id, charter=json.dumps(charter.model_dump() if charter else {}),
        )
        workspace_root = self.sandboxes_root / actuation_id / agent.id / "workspace"
        # F13: the assignment tree lives at an actuation-independent path (team + node), so the
        # CLI's per-directory conversation key — and with it --resume — survives re-actuation.
        if self.home_resolver is not None:
            node_work_root = self.home_resolver(top.id) / "work" / agent.id
        else:
            node_work_root = self.work_root / top.id / agent.id
        node_work_root.mkdir(parents=True, exist_ok=True)
        runtime_kind = self._node_runtime(top, agent)
        spec = SandboxSpec(
            actuation_id=actuation_id, node_id=agent.id, team_id=top.id,
            workspace_root=workspace_root,
            log_dir=node_work_root / "logs",  # F16: the adapter log outlives the actuation
            env=self._build_env(token, agent.id, actuation_id, runtime_kind=runtime_kind,
                                model=profile.model if profile else None,
                                work_root=node_work_root),
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

    def _build_env(
        self, token: str, node_id: str, actuation_id: str, *, runtime_kind: str = "loop",
        model: str | None = None, work_root: Path | None = None,
    ) -> dict[str, str]:
        env = {
            "CANOPY_CP_URL": self.cp_url,
            "CANOPY_RUN_TOKEN": token,
            "CANOPY_NODE_ID": node_id,
            "CANOPY_ACTUATION_ID": actuation_id,
            "CANOPY_A2A_HOST": "127.0.0.1",
            "CANOPY_A2A_PORT": "0",  # bind ephemeral, report endpoint at register
            "CANOPY_RUNTIME": runtime_kind,
        }
        if work_root is not None:
            env["CANOPY_WORK_ROOT"] = str(work_root)
        if self.agent_pythonpath:
            env["PYTHONPATH"] = self.agent_pythonpath
        # Minimal host vars needed for the interpreter to start (Windows needs SystemRoot).
        passthrough = ["PATH", "SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "PYTHONHOME"]
        if runtime_kind == "cli-claude":
            # The CLI needs its (operator-provisioned) auth/config dir and a home
            # (cli-runtime.md §8: trusted-local, stated plainly), plus the shim override.
            # USER/LOGNAME are load-bearing on macOS: without USER the CLI cannot reach
            # its Keychain credentials and every session exits "not logged in".
            passthrough += ["CLAUDE_CONFIG_DIR", "CANOPY_CLI_CMD", "FAKE_CLAUDE_SCRIPT",
                            "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                            "USER", "LOGNAME", "TMPDIR", "LANG"]
            if model:
                env["CANOPY_CLI_MODEL"] = model
        for key in passthrough:
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
        if self.router is not None:
            self.router.clear_actuation(actuation_id)  # drop channels + drain queues
        self.directory.remove_actuation(actuation_id)
        self._set_state(actuation_id, "stopped")
        row = self._actuation_row(actuation_id)
        if row:
            self.activity.log("operator", "actuation.stopped", team_id=row["team_id"],
                              subject_ids=[actuation_id])

    # -- reconciler --------------------------------------------------------- #
    async def reconcile_once(self, actuation_id: str) -> None:
        row = self._actuation_row(actuation_id)
        if row is None or row["state"] not in _ACTIVE_STATES:
            return
        threshold = (datetime.now(UTC) - timedelta(seconds=_STALE_SECONDS)).isoformat().replace(
            "+00:00", "Z"
        )
        try:
            team = self.store.read(row["team_id"])
        except StoreError:
            # Orphaned actuation (its team was deleted underneath it) — fail it so it stops
            # occupying every future reconciler pass (E6: one zombie must not starve the fleet).
            self._set_state(actuation_id, "failed")
            self.activity.log("system", "actuation.orphaned", team_id=row["team_id"],
                              subject_ids=[actuation_id])
            return
        agents_by_id = {a.id: (p, a) for p, a in enumerate_nodes(team)}
        recovered_any = False
        for stale in self.directory.stale(actuation_id, threshold):
            node = self._node(actuation_id, stale.nodeId)
            if node is None or node["attempts"] >= _MAX_RESTARTS:
                continue
            found = agents_by_id.get(stale.nodeId)
            if not found:
                continue
            team_path, agent = found
            self._bump_attempts(actuation_id, stale.nodeId)
            self.activity.log("system", "actuation.node_restart", team_id=team.id,
                              subject_ids=[actuation_id, stale.nodeId])
            await self._restart_node(actuation_id, node)
            await self._provision_node(actuation_id, team, team_path, agent)
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
    def get_current(self, team_id: str) -> ActuationView | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM actuation WHERE team_id=? AND state NOT IN ('stopped','failed') "
                "ORDER BY created_at DESC LIMIT 1",
                (team_id,),
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
                nodeId=n["node_id"], teamPath=json.loads(n["team_path"]), subState=n["sub_state"],
                status=d.status if d else None, endpointUrl=d.endpointUrl if d else None,
                error=n["error"],
            ))
        return ActuationView(
            id=row["id"], teamId=row["team_id"], state=row["state"], error=row["error"],
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

    def _insert_node(self, actuation_id: str, node_id: str, team_path: list[str]) -> None:
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO actuation_node (actuation_id, node_id, team_path, "
                "sub_state, created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?)",
                (actuation_id, node_id, json.dumps(team_path), ts, ts),
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
