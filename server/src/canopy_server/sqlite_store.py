"""SQLite-backed organization document store.

Same interface as the phase-1 :class:`~canopy_server.store.JsonFileStore`, so the phase-1 REST
contract in ``routes/organizations.py`` is unchanged (topology.md §1: "the phase-1 REST contract
is unchanged"). A document is stored whole as JSON in one row — its internal chart structure is
the domain of the models and validators, not of the schema — with ``updated_at`` mirrored into a
column for cheap listing.

On construction it performs a **non-destructive** one-time migration of any phase-1
``organizations/*.json`` files into the table (documents whose id is already present are left
alone; the JSON files are never modified or deleted). That makes ``pnpm dev`` on an existing
phase-1 checkout Just Work while keeping the old files as a backup.
"""

from __future__ import annotations

import json
from pathlib import Path

from .db import Db, register_schema
from .models import Organization
from .store import NotFound  # reuse the phase-1 exception so route `except NotFound` still catches

SCHEMA = """
CREATE TABLE IF NOT EXISTS organizations (
    id          TEXT PRIMARY KEY,
    document    TEXT NOT NULL,
    updated_at  TEXT
);
"""
register_schema(SCHEMA)


class SqliteOrgStore:
    def __init__(self, db: Db, *, migrate_from: Path | None = None):
        self.db = db
        if migrate_from is not None:
            self._migrate_json_dir(migrate_from)

    # -- reads -------------------------------------------------------------- #
    def exists(self, doc_id: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM organizations WHERE id = ?", (doc_id,)
            ).fetchone()
            return row is not None

    def list_ids(self) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT id FROM organizations ORDER BY id").fetchall()
            return [r["id"] for r in rows]

    def read_raw(self, doc_id: str) -> dict:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT document FROM organizations WHERE id = ?", (doc_id,)
            ).fetchone()
        if row is None:
            raise NotFound(doc_id)
        return json.loads(row["document"])

    def read(self, doc_id: str) -> Organization:
        return Organization.model_validate(self.read_raw(doc_id))

    def read_all(self) -> list[Organization]:
        out: list[Organization] = []
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT document FROM organizations ORDER BY id"
            ).fetchall()
        for r in rows:
            try:
                out.append(Organization.model_validate(json.loads(r["document"])))
            except Exception:
                # A malformed row should not take down the whole list (matches JsonFileStore).
                continue
        return out

    # -- writes ------------------------------------------------------------- #
    def write(self, org: Organization) -> None:
        payload = json.dumps(org.model_dump(by_alias=True, mode="json"), ensure_ascii=False)
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO organizations (id, document, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET document = excluded.document, "
                "updated_at = excluded.updated_at",
                (org.id, payload, org.updatedAt),
            )

    def delete(self, doc_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM organizations WHERE id = ?", (doc_id,))
            return cur.rowcount > 0

    # -- migration ---------------------------------------------------------- #
    def _migrate_json_dir(self, json_dir: Path) -> None:
        if not json_dir.is_dir():
            return
        existing = set(self.list_ids())
        for path in sorted(json_dir.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                org = Organization.model_validate(doc)
            except Exception:
                continue
            if org.id in existing:
                continue
            self.write(org)
            existing.add(org.id)
