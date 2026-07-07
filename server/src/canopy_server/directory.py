"""Agent Directory — the registry of live agents (control-plane.md §3).

Maps ``{actuationId, agentNodeId} -> {endpointUrl, agentCard, status, lastHeartbeatAt}``. It is
what the router consults for where-to-deliver (A3) and what the UI reads for live chart badges.
Status is the domain's observable set: ``provisioning | idle | engaged | gated | paused | dead``.
``gated`` (a Phase-3 addition — debt D2) means the node is suspended on a Gate and consuming
nothing; the heartbeat payload carries ``gateKind`` for the chart badge. Existing values keep
their meanings (the debt rule: phase-3 only adds, never repurposes). Agents heartbeat every 10 s;
the Actuator's reconciler treats a stale heartbeat as liveness loss (control-plane.md §2).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel

from .db import Db, register_schema
from .deps import now_iso

AgentStatus = Literal["provisioning", "idle", "engaged", "gated", "paused", "dead"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS directory_agent (
    actuation_id      TEXT NOT NULL,
    node_id           TEXT NOT NULL,
    endpoint_url      TEXT,
    agent_card        TEXT,
    status            TEXT NOT NULL DEFAULT 'provisioning',
    last_heartbeat_at TEXT,
    created_at        TEXT NOT NULL,
    PRIMARY KEY (actuation_id, node_id)
);
"""
register_schema(SCHEMA)


class DirectoryAgent(BaseModel):
    actuationId: str
    nodeId: str
    endpointUrl: str | None
    agentCard: dict[str, Any] | None
    status: AgentStatus
    lastHeartbeatAt: str | None
    createdAt: str


def _row(r) -> DirectoryAgent:
    return DirectoryAgent(
        actuationId=r["actuation_id"],
        nodeId=r["node_id"],
        endpointUrl=r["endpoint_url"],
        agentCard=json.loads(r["agent_card"]) if r["agent_card"] else None,
        status=r["status"],
        lastHeartbeatAt=r["last_heartbeat_at"],
        createdAt=r["created_at"],
    )


class AgentDirectory:
    def __init__(self, db: Db):
        self.db = db

    def upsert_provisioning(self, actuation_id: str, node_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO directory_agent (actuation_id, node_id, status, created_at) "
                "VALUES (?, ?, 'provisioning', ?) "
                "ON CONFLICT(actuation_id, node_id) DO UPDATE SET status='provisioning'",
                (actuation_id, node_id, now_iso()),
            )

    def register(
        self, actuation_id: str, node_id: str, endpoint_url: str, agent_card: dict[str, Any]
    ) -> None:
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE directory_agent SET endpoint_url=?, agent_card=?, status='idle', "
                "last_heartbeat_at=? WHERE actuation_id=? AND node_id=?",
                (endpoint_url, json.dumps(agent_card), ts, actuation_id, node_id),
            )

    def heartbeat(
        self, actuation_id: str, node_id: str, status: AgentStatus | None = None
    ) -> None:
        ts = now_iso()
        with self.db.transaction() as conn:
            if status is not None:
                conn.execute(
                    "UPDATE directory_agent SET last_heartbeat_at=?, status=? "
                    "WHERE actuation_id=? AND node_id=?",
                    (ts, status, actuation_id, node_id),
                )
            else:
                conn.execute(
                    "UPDATE directory_agent SET last_heartbeat_at=? "
                    "WHERE actuation_id=? AND node_id=?",
                    (ts, actuation_id, node_id),
                )

    def set_status(self, actuation_id: str, node_id: str, status: AgentStatus) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE directory_agent SET status=? WHERE actuation_id=? AND node_id=?",
                (status, actuation_id, node_id),
            )

    def get(self, actuation_id: str, node_id: str) -> DirectoryAgent | None:
        with self.db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM directory_agent WHERE actuation_id=? AND node_id=?",
                (actuation_id, node_id),
            ).fetchone()
        return _row(r) if r else None

    def list(self, actuation_id: str) -> list[DirectoryAgent]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM directory_agent WHERE actuation_id=? ORDER BY node_id",
                (actuation_id,),
            ).fetchall()
        return [_row(r) for r in rows]

    def stale(self, actuation_id: str, older_than_iso: str) -> list[DirectoryAgent]:
        """Agents whose last heartbeat predates ``older_than_iso`` (ISO strings sort lexically)."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM directory_agent WHERE actuation_id=? AND status != 'dead' AND "
                "(last_heartbeat_at IS NULL OR last_heartbeat_at < ?)",
                (actuation_id, older_than_iso),
            ).fetchall()
        return [_row(r) for r in rows]

    def remove_actuation(self, actuation_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM directory_agent WHERE actuation_id=?", (actuation_id,))
