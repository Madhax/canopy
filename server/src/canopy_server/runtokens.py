"""Run tokens — the least-privilege identity every agent carries (sandbox.md §2, §5).

A run token is a random 256-bit secret, **stored only as a SHA-256 hash**, scoped to one
``{actuationId, agentNodeId}``. It is minted when a node is provisioned and revoked at teardown.
It exists so an agent can act only as *itself* — an agent process holds no API key (invariant 10),
so a leaked env leaks only this revocable token, never a credential.

The token carries node *identity* (stable), not configuration: the gateway resolves the current
binding → profile → secret from the node identity at call time, so a profile edit takes effect on
the next call without reissuing tokens (agent-profile.md §4). ``default_meter_id`` is an A1
convenience (one standing meter per node before the Actuator exists); from A4 the meter comes from
the task context and this field is ignored.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from .db import Db, register_schema
from .deps import now_iso
from .ids import new_run_token, new_run_token_record_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS runtoken (
    id               TEXT PRIMARY KEY,
    actuation_id     TEXT NOT NULL,
    node_id          TEXT NOT NULL,
    org_id           TEXT NOT NULL,
    org_path         TEXT NOT NULL DEFAULT '[]',
    default_meter_id TEXT,
    token_hash       TEXT NOT NULL UNIQUE,
    revoked          INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_runtoken_actuation ON runtoken (actuation_id);
"""
register_schema(SCHEMA)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RunTokenRecord(BaseModel):
    id: str
    actuationId: str
    nodeId: str
    orgId: str
    orgPath: list[str]
    defaultMeterId: str | None
    revoked: bool
    createdAt: str


def _row_to_record(row) -> RunTokenRecord:
    import json

    return RunTokenRecord(
        id=row["id"],
        actuationId=row["actuation_id"],
        nodeId=row["node_id"],
        orgId=row["org_id"],
        orgPath=json.loads(row["org_path"]),
        defaultMeterId=row["default_meter_id"],
        revoked=bool(row["revoked"]),
        createdAt=row["created_at"],
    )


class RunTokenStore:
    def __init__(self, db: Db):
        self.db = db

    def issue(
        self,
        actuation_id: str,
        node_id: str,
        org_id: str,
        *,
        org_path: list[str] | None = None,
        default_meter_id: str | None = None,
    ) -> tuple[str, RunTokenRecord]:
        """Mint a token; returns ``(plaintext_token, record)``. The plaintext is never stored."""
        import json

        token = new_run_token()
        rid = new_run_token_record_id()
        ts = now_iso()
        path = org_path or []
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO runtoken (id, actuation_id, node_id, org_id, org_path, "
                "default_meter_id, token_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, actuation_id, node_id, org_id, json.dumps(path), default_meter_id,
                 _hash(token), ts),
            )
        record = RunTokenRecord(
            id=rid, actuationId=actuation_id, nodeId=node_id, orgId=org_id, orgPath=path,
            defaultMeterId=default_meter_id, revoked=False, createdAt=ts,
        )
        return token, record

    def resolve(self, token: str) -> RunTokenRecord | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM runtoken WHERE token_hash = ? AND revoked = 0", (_hash(token),)
            ).fetchone()
        return _row_to_record(row) if row else None

    def revoke(self, record_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("UPDATE runtoken SET revoked = 1 WHERE id = ?", (record_id,))
            return cur.rowcount > 0

    def revoke_actuation(self, actuation_id: str) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE runtoken SET revoked = 1 WHERE actuation_id = ?", (actuation_id,)
            )
            return cur.rowcount
