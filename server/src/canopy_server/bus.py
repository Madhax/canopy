"""The distribution Bus — the scalability seam (data-plane.md §3).

A2A is point-to-point; it has no work distribution, queueing, or fan-out. That is *our* layer: the
Bus. v1 is `SqliteBus`; Redis Streams / NATS / managed pub-sub swap in behind the same ABC later
(roadmap.md) — and the agent runtime never changes across any of them, which is the test the design
must keep passing.

The queue semantics are modeled on Paperclip's `agent_wakeup_requests` (the DX reference this repo
cites): a durable per-topic FIFO with an atomic claim + visibility timeout, plus two robustness
features that queue proved worth having —

* **Idempotency keys** — a redelivered publish (crash between enqueue and ack) collapses to one
  queued message instead of a duplicate (risk AR-3).
* **Coalescing** — many nudges to the same busy node while one is already queued bump a counter
  instead of piling up N rows (Paperclip's `coalescedCount`), so a hot node's inbox can't explode.

Semantics: at-least-once, per-topic FIFO, visibility timeout on poll, dead-letter after N nacks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from .db import Db, register_schema
from .deps import now_iso
from .ids import new_message_id
from .registry import Registry

SCHEMA = """
CREATE TABLE IF NOT EXISTS router_queue (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    id              TEXT NOT NULL UNIQUE,
    topic           TEXT NOT NULL,
    envelope        TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'ready',   -- ready | locked | acked | dead
    locked_until    TEXT,
    consumer        TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    idempotency_key TEXT,
    coalesce_key    TEXT,
    coalesced_count INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_queue_topic_state ON router_queue (topic, state, seq);
CREATE UNIQUE INDEX IF NOT EXISTS ux_queue_idem ON router_queue (topic, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
"""
register_schema(SCHEMA)


class Envelope(BaseModel):
    id: str
    actuationId: str
    fromNodeId: str
    toNodeId: str
    kind: str = "a2a"
    a2aPayload: dict[str, Any] = Field(default_factory=dict)
    taskRef: str | None = None
    ts: str


class Delivery(BaseModel):
    id: str  # delivery id == the queue row id (used to ack/nack)
    topic: str
    envelope: Envelope
    attempts: int
    coalescedCount: int = 0


class Bus(ABC):
    @abstractmethod
    def publish(self, topic: str, envelope: Envelope, *, idempotency_key: str | None = None,
                coalesce_key: str | None = None, max_attempts: int = 5) -> str: ...

    @abstractmethod
    def poll(self, topic: str, consumer: str, max_n: int, ttl_s: int) -> list[Delivery]: ...

    @abstractmethod
    def ack(self, delivery_id: str) -> None: ...

    @abstractmethod
    def nack(self, delivery_id: str, requeue: bool) -> tuple[bool, Envelope | None]:
        """Return ``(dead_lettered, envelope)`` — envelope present only when it hit the DLQ."""

    @abstractmethod
    def depth(self, topic: str) -> int:
        """Ready + locked messages on a topic (the operator's visible bottleneck signal)."""


bus_registry: Registry[Bus] = Registry("bus")


def _now_plus(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


@bus_registry.register("sqlite")
class SqliteBus(Bus):
    def __init__(self, db: Db):
        self.db = db

    def publish(self, topic, envelope, *, idempotency_key=None, coalesce_key=None,
                max_attempts=5) -> str:
        payload = envelope.model_dump_json()
        ts = now_iso()
        with self.db.transaction() as conn:
            if idempotency_key is not None:
                existing = conn.execute(
                    "SELECT id FROM router_queue WHERE topic=? AND idempotency_key=?",
                    (topic, idempotency_key),
                ).fetchone()
                if existing:
                    return existing["id"]
            if coalesce_key is not None:
                ready = conn.execute(
                    "SELECT id FROM router_queue WHERE topic=? AND coalesce_key=? AND state='ready'"
                    " ORDER BY seq LIMIT 1",
                    (topic, coalesce_key),
                ).fetchone()
                if ready:
                    conn.execute(
                        "UPDATE router_queue SET coalesced_count = coalesced_count + 1, "
                        "envelope=?, updated_at=? WHERE id=?",
                        (payload, ts, ready["id"]),
                    )
                    return ready["id"]
            mid = envelope.id or new_message_id()
            conn.execute(
                "INSERT INTO router_queue (id, topic, envelope, max_attempts, idempotency_key, "
                "coalesce_key, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (mid, topic, payload, max_attempts, idempotency_key, coalesce_key, ts, ts),
            )
        return mid

    def poll(self, topic, consumer, max_n, ttl_s) -> list[Delivery]:
        now = now_iso()
        out: list[Delivery] = []
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM router_queue WHERE topic=? AND state IN ('ready','locked') AND "
                "(state='ready' OR locked_until < ?) ORDER BY seq LIMIT ?",
                (topic, now, max_n),
            ).fetchall()
            for r in rows:
                conn.execute(
                    "UPDATE router_queue SET state='locked', locked_until=?, consumer=?, "
                    "attempts=attempts+1, updated_at=? WHERE id=?",
                    (_now_plus(ttl_s), consumer, now, r["id"]),
                )
                out.append(Delivery(
                    id=r["id"], topic=topic, envelope=Envelope.model_validate_json(r["envelope"]),
                    attempts=r["attempts"] + 1, coalescedCount=r["coalesced_count"],
                ))
        return out

    def ack(self, delivery_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE router_queue SET state='acked', updated_at=? WHERE id=?",
                (now_iso(), delivery_id),
            )

    def nack(self, delivery_id: str, requeue: bool) -> tuple[bool, Envelope | None]:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM router_queue WHERE id=?", (delivery_id,)
            ).fetchone()
            if row is None:
                return False, None
            envelope = Envelope.model_validate_json(row["envelope"])
            if requeue and row["attempts"] < row["max_attempts"]:
                conn.execute(
                    "UPDATE router_queue SET state='ready', locked_until=NULL, consumer=NULL, "
                    "updated_at=? WHERE id=?",
                    (now_iso(), delivery_id),
                )
                return False, None
            conn.execute(
                "UPDATE router_queue SET state='dead', updated_at=? WHERE id=?",
                (now_iso(), delivery_id),
            )
        return True, envelope

    def depth(self, topic: str) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM router_queue WHERE topic=? AND state IN "
                "('ready','locked')",
                (topic,),
            ).fetchone()
        return int(row["n"])
