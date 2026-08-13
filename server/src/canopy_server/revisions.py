"""Team document revisions — the safety net under every overwrite.

Every destructive write to a team document (autosave replacing the stored copy, a
conflict-dialog overwrite, a restore, a delete) first snapshots the *previous* stored
version here. Accidents stop being losses: any of the last ``KEEP`` versions is one
restore away. Append-only with a small retention cap; rows survive team deletion so a
deleted team is recoverable too.

Born from a live operator incident (2026-08-10): a double-click stamped a formation over
an existing chart, autosave persisted the accident within a second, and the undo path
handed the operator a conflict dialog whose every option lost one side. The palette and
undo bugs are fixed in the UI; this module is the structural guarantee that the next
accident — whatever shape it takes — is recoverable.
"""

from __future__ import annotations

import json
from typing import Any

from .db import Db, register_schema
from .ids import new_revision_id

KEEP = 20  # retained revisions per team

SCHEMA = """
CREATE TABLE IF NOT EXISTS team_revision (
    id        TEXT PRIMARY KEY,
    team_id   TEXT NOT NULL,
    reason    TEXT NOT NULL DEFAULT 'save',   -- save | overwrite | restore | delete
    document  TEXT NOT NULL,
    saved_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_revision_team ON team_revision (team_id, saved_at DESC);
"""
register_schema(SCHEMA)


def snapshot(db: Db, team_id: str, document: dict[str, Any], *, reason: str,
             now: str) -> str:
    """Record the given (previous) document as a revision and trim to ``KEEP``."""
    rid = new_revision_id()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO team_revision (id, team_id, reason, document, saved_at)"
            " VALUES (?,?,?,?,?)",
            (rid, team_id, reason, json.dumps(document, ensure_ascii=False), now),
        )
        conn.execute(
            "DELETE FROM team_revision WHERE team_id = ? AND id NOT IN ("
            " SELECT id FROM team_revision WHERE team_id = ?"
            " ORDER BY saved_at DESC, id DESC LIMIT ?)",
            (team_id, team_id, KEEP),
        )
    return rid


def list_revisions(db: Db, team_id: str) -> list[dict[str, Any]]:
    """Newest first: id, reason, savedAt, and a summary (name + agent count) per row."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, reason, document, saved_at FROM team_revision WHERE team_id = ?"
            " ORDER BY saved_at DESC, id DESC",
            (team_id,),
        ).fetchall()
    out = []
    for r in rows:
        doc = json.loads(r["document"])
        agents = doc.get("agents", [])
        out.append({
            "id": r["id"], "reason": r["reason"], "savedAt": r["saved_at"],
            "name": doc.get("name", ""), "agentCount": len(agents),
            "updatedAt": doc.get("updatedAt"),
        })
    return out


def get_revision(db: Db, team_id: str, revision_id: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT document FROM team_revision WHERE team_id = ? AND id = ?",
            (team_id, revision_id),
        ).fetchone()
    return json.loads(row["document"]) if row else None
