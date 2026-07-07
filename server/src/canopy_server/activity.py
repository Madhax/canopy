"""Activity Log — append-only audit events (control-plane.md §8).

Every mutating action and lifecycle transition lands here: actuation state changes, registrations,
message deliveries (metadata only — bodies live in the router), budget warns/stops, artifact
publishes, intent submissions. It backs the UI activity feed (A5) and is the audit substrate the
domain's invariants lean on. Append-only by construction: there is no update or delete.
"""

from __future__ import annotations

import json
from typing import Any

from .db import Db, register_schema
from .deps import now_iso
from .ids import new_activity_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_event (
    id          TEXT PRIMARY KEY,
    seq         INTEGER,
    ts          TEXT NOT NULL,
    org_id      TEXT,
    actor       TEXT NOT NULL,
    kind        TEXT NOT NULL,
    subject_ids TEXT NOT NULL DEFAULT '[]',
    payload     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_activity_org ON activity_event (org_id, seq);
"""
register_schema(SCHEMA)


class ActivityLog:
    def __init__(self, db: Db):
        self.db = db

    def log(
        self,
        actor: str,
        kind: str,
        *,
        org_id: str | None = None,
        subject_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM activity_event"
            ).fetchone()
            conn.execute(
                "INSERT INTO activity_event (id, seq, ts, org_id, actor, kind, subject_ids, "
                "payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_activity_id(), row["n"], now_iso(), org_id, actor, kind,
                    json.dumps(subject_ids or []), json.dumps(payload or {}),
                ),
            )

    def list(
        self, org_id: str | None = None, *, after_seq: int = 0, limit: int = 100
    ) -> list[dict]:
        with self.db.connect() as conn:
            if org_id is None:
                rows = conn.execute(
                    "SELECT * FROM activity_event WHERE seq > ? ORDER BY seq LIMIT ?",
                    (after_seq, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM activity_event WHERE org_id = ? AND seq > ? ORDER BY seq "
                    "LIMIT ?",
                    (org_id, after_seq, limit),
                ).fetchall()
        return [
            {
                "id": r["id"],
                "seq": r["seq"],
                "ts": r["ts"],
                "orgId": r["org_id"],
                "actor": r["actor"],
                "kind": r["kind"],
                "subjectIds": json.loads(r["subject_ids"]),
                "payload": json.loads(r["payload"]),
            }
            for r in rows
        ]
