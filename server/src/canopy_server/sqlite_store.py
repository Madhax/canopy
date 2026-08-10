"""SQLite-backed team document store.

Same interface as the phase-1 :class:`~canopy_server.store.JsonFileStore`, so the phase-1 REST
contract in ``routes/teams.py`` is unchanged in semantics (re-rooted to ``/teams`` at C1). A
document is stored whole as JSON in one row — its internal chart structure is the domain of the
models and validators, not of the schema — with ``updated_at`` mirrored into a column for cheap
listing and ``organization_id`` carrying the team's Organization membership (server-side state,
never part of the document — design/organizations/01 §4).

Boot migrations, all non-destructive and idempotent (design/organizations/07 §2.3):

* phase-1 ``organizations/*.json`` files import into the table (kept on disk as backup);
* the pre-C1 ``organizations`` table renames to ``teams`` and gains ``organization_id``;
* every existing team is assigned to the ``default`` Organization;
* stored v1 documents rewrite to v2 through :func:`~canopy_server.migrate.migrate_team`
  (the JSON-file backups keep the v1 originals).
"""

from __future__ import annotations

import json
from pathlib import Path

from .db import Db, register_schema
from .migrate import migrate_team
from .models import Team
from .orgs import ensure_default_org
from .store import NotFound  # reuse the phase-1 exception so route `except NotFound` still catches

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id               TEXT PRIMARY KEY,
    document         TEXT NOT NULL,
    updated_at       TEXT,
    organization_id  TEXT
);
"""
register_schema(SCHEMA)


def _now_iso() -> str:  # local import to avoid a deps<->store import cycle
    from .deps import now_iso

    return now_iso()


class SqliteTeamStore:
    def __init__(self, db: Db, *, migrate_from: Path | None = None):
        self.db = db
        self._migrate_table_rename()
        self.default_org_id = ensure_default_org(db, now=_now_iso)
        self._migrate_membership_and_documents()
        if migrate_from is not None:
            self._migrate_json_dir(migrate_from)

    # -- reads -------------------------------------------------------------- #
    def exists(self, doc_id: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute("SELECT 1 FROM teams WHERE id = ?", (doc_id,)).fetchone()
            return row is not None

    def list_ids(self) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT id FROM teams ORDER BY id").fetchall()
            return [r["id"] for r in rows]

    def read_raw(self, doc_id: str) -> dict:
        with self.db.connect() as conn:
            row = conn.execute("SELECT document FROM teams WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            raise NotFound(doc_id)
        return migrate_team(json.loads(row["document"]))

    def read(self, doc_id: str) -> Team:
        return Team.model_validate(self.read_raw(doc_id))

    def read_all(self) -> list[Team]:
        out: list[Team] = []
        with self.db.connect() as conn:
            rows = conn.execute("SELECT document FROM teams ORDER BY id").fetchall()
        for r in rows:
            try:
                out.append(Team.model_validate(migrate_team(json.loads(r["document"]))))
            except Exception:
                # A malformed row should not take down the whole list (matches JsonFileStore).
                continue
        return out

    # -- membership (server-side state; design/organizations/01 §4) ---------- #
    def organization_of(self, doc_id: str) -> str:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT organization_id FROM teams WHERE id = ?", (doc_id,)
            ).fetchone()
        if row is None:
            raise NotFound(doc_id)
        return row["organization_id"] or self.default_org_id

    def ids_in_organization(self, org_id: str) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM teams WHERE organization_id = ? ORDER BY id", (org_id,)
            ).fetchall()
        return [r["id"] for r in rows]

    def move_to_organization(self, doc_id: str, org_id: str) -> None:
        """Custody transfer (design/organizations/01 §3): the route layer enforces
        not-actuated and writes the audit row; this class only stores."""
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE teams SET organization_id = ? WHERE id = ?", (org_id, doc_id)
            )
            if cur.rowcount == 0:
                raise NotFound(doc_id)

    # -- writes ------------------------------------------------------------- #
    def write(self, team: Team, *, organization_id: str | None = None) -> None:
        payload = json.dumps(team.model_dump(by_alias=True, mode="json"), ensure_ascii=False)
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO teams (id, document, updated_at, organization_id)"
                " VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET document = excluded.document, "
                "updated_at = excluded.updated_at, "
                "organization_id = COALESCE(excluded.organization_id, teams.organization_id)",
                (team.id, payload, team.updatedAt, organization_id),
            )
            # A fresh row with no membership stated lands in the default Organization.
            conn.execute(
                "UPDATE teams SET organization_id = ? WHERE id = ? AND organization_id IS NULL",
                (self.default_org_id, team.id),
            )

    def delete(self, doc_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM teams WHERE id = ?", (doc_id,))
            return cur.rowcount > 0

    # -- boot migrations ---------------------------------------------------- #
    def _migrate_table_rename(self) -> None:
        """Pre-C1 DBs have an ``organizations`` table; carry its rows into ``teams`` once."""
        with self.db.transaction() as conn:
            names = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "organizations" in names:
                if "teams" in names:
                    # ensure_schema already created the (empty) new table; keep the old data.
                    n = conn.execute("SELECT COUNT(*) AS n FROM teams").fetchone()["n"]
                    if n == 0:
                        conn.execute("DROP TABLE teams")
                        conn.execute("ALTER TABLE organizations RENAME TO teams")
                else:
                    conn.execute("ALTER TABLE organizations RENAME TO teams")
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(teams)").fetchall()}
            if "organization_id" not in cols:
                conn.execute("ALTER TABLE teams ADD COLUMN organization_id TEXT")

    def _migrate_membership_and_documents(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE teams SET organization_id = ? WHERE organization_id IS NULL",
                (self.default_org_id,),
            )
            rows = conn.execute("SELECT id, document FROM teams").fetchall()
            for r in rows:
                doc = json.loads(r["document"])
                if doc.get("kind") == "canopy.organization" or doc.get("schemaVersion", 1) < 2:
                    migrated = migrate_team(doc)
                    conn.execute(
                        "UPDATE teams SET document = ? WHERE id = ?",
                        (json.dumps(migrated, ensure_ascii=False), r["id"]),
                    )

    def _migrate_json_dir(self, json_dir: Path) -> None:
        if not json_dir.is_dir():
            return
        existing = set(self.list_ids())
        for path in sorted(json_dir.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                team = Team.model_validate(migrate_team(doc))
            except Exception:
                continue
            if team.id in existing:
                continue
            self.write(team)
            existing.add(team.id)


# Back-compat alias for any straggling import; the C1 sweep removes uses.
SqliteOrgStore = SqliteTeamStore
