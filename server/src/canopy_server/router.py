"""Message Router — mediated A2A, chart topology enforcement (data-plane.md §1–2).

The domain forbids unmediated channels (invariant 3): every A2A message is POSTed to the router,
which validates the channel against the chart and forwards via the Bus. Agents never learn peer
addresses — only node ids. Channels are derived from the actuated chart:

- ``manager↔report`` — always, both directions.
- ``operator↔any`` — the operator (UI/API) may address any node.
- ``team broadcast`` — a manager may fan one message to all its reports (the router does the N
  enqueues, the first place the bus visibly beats point-to-point).
- everything else is **rejected** (403 CHANNEL_FORBIDDEN, with the domain's own explanation:
  route via the common manager). Sub-org opacity is enforced here too — no channel crosses into a
  child org's internals; the child root "looks like any other report" to its mount agent.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .bus import Bus, Envelope
from .db import Db, register_schema
from .deps import now_iso
from .ids import new_message_id
from .models import Organization

OPERATOR = "operator"

SCHEMA = """
CREATE TABLE IF NOT EXISTS router_channel (
    actuation_id TEXT NOT NULL,
    from_node    TEXT NOT NULL,
    to_node      TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'manager_report',
    PRIMARY KEY (actuation_id, from_node, to_node)
);

CREATE TABLE IF NOT EXISTS router_message (
    id           TEXT PRIMARY KEY,
    actuation_id TEXT NOT NULL,
    from_node    TEXT NOT NULL,
    to_node      TEXT NOT NULL,
    kind         TEXT NOT NULL,
    task_ref     TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_message_actuation ON router_message (actuation_id, created_at);
"""
register_schema(SCHEMA)


class ChannelForbidden(Exception):
    code = "CHANNEL_FORBIDDEN"

    def __init__(self, from_node: str, to_node: str):
        self.fromNode = from_node
        self.toNode = to_node
        super().__init__(
            f"no channel {from_node} → {to_node}: communication follows the chart — "
            "route this through the common manager."
        )


def inbox_topic(actuation_id: str, node_id: str) -> str:
    return f"act.{actuation_id}.agent.{node_id}.inbox"


class SentMessage(BaseModel):
    messageId: str
    topic: str


def _walk(org: Organization, path: list[str]):
    yield org, path
    for child in org.childOrganizations:
        yield from _walk(child.organization, path + [child.organization.id])


class MessageRouter:
    def __init__(self, db: Db, bus: Bus):
        self.db = db
        self.bus = bus

    # -- channel derivation ------------------------------------------------- #
    def derive_channels(self, actuation_id: str, top: Organization) -> None:
        # (from, to, kind) — "down" is manager→report (delegation), "up" is report→manager
        # (delivery/escalation). The kind lets broadcast fan out to reports only, never upward.
        pairs: list[tuple[str, str, str]] = []
        for org, _path in _walk(top, []):
            for agent in org.agents:
                if agent.managerId is not None:
                    pairs.append((agent.managerId, agent.id, "down"))
                    pairs.append((agent.id, agent.managerId, "up"))
            for child in org.childOrganizations:
                root_id = child.organization.id  # a mounted child org == its root, as a report
                pairs.append((child.mountAgentId, root_id, "down"))
                pairs.append((root_id, child.mountAgentId, "up"))
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM router_channel WHERE actuation_id=?", (actuation_id,))
            for frm, to, kind in pairs:
                conn.execute(
                    "INSERT OR IGNORE INTO router_channel (actuation_id, from_node, to_node, kind) "
                    "VALUES (?, ?, ?, ?)",
                    (actuation_id, frm, to, kind),
                )

    def channel_allowed(self, actuation_id: str, from_node: str, to_node: str) -> bool:
        if from_node == OPERATOR:
            return True  # operator↔any
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM router_channel WHERE actuation_id=? AND from_node=? AND to_node=?",
                (actuation_id, from_node, to_node),
            ).fetchone()
        return row is not None

    def reports_of(self, actuation_id: str, manager_node: str) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT to_node FROM router_channel WHERE actuation_id=? AND from_node=? AND "
                "kind='down'",
                (actuation_id, manager_node),
            ).fetchall()
        return [r["to_node"] for r in rows]

    # -- send --------------------------------------------------------------- #
    def send(self, actuation_id: str, from_node: str, to_node: str, a2a_payload: dict[str, Any],
             *, kind: str = "a2a", task_ref: str | None = None,
             idempotency_key: str | None = None) -> SentMessage:
        if not self.channel_allowed(actuation_id, from_node, to_node):
            raise ChannelForbidden(from_node, to_node)
        mid = new_message_id()
        envelope = Envelope(
            id=mid, actuationId=actuation_id, fromNodeId=from_node, toNodeId=to_node,
            kind=kind, a2aPayload=a2a_payload, taskRef=task_ref, ts=now_iso(),
        )
        topic = inbox_topic(actuation_id, to_node)
        self.bus.publish(topic, envelope, idempotency_key=idempotency_key)
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO router_message (id, actuation_id, from_node, to_node, kind, task_ref, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, actuation_id, from_node, to_node, kind, task_ref, now_iso()),
            )
        return SentMessage(messageId=mid, topic=topic)

    def broadcast(self, actuation_id: str, from_manager: str,
                  a2a_payload: dict[str, Any]) -> list[SentMessage]:
        return [
            self.send(actuation_id, from_manager, report, a2a_payload, kind="broadcast")
            for report in self.reports_of(actuation_id, from_manager)
        ]

    def depth(self, actuation_id: str, node_id: str) -> int:
        return self.bus.depth(inbox_topic(actuation_id, node_id))

    def clear_actuation(self, actuation_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM router_channel WHERE actuation_id=?", (actuation_id,))
            conn.execute(
                "DELETE FROM router_queue WHERE topic LIKE ?", (f"act.{actuation_id}.%",)
            )
