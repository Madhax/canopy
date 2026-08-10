"""Organizations — the umbrella entity above Teams (design/organizations/01, milestone C1).

An Organization is a named, budgeted, **isolated** group of Teams: identity + theme + priority
class + budget, and nothing else. It is never actuated, has no chart, and cannot receive an
Intent (invariant 12). Membership lives server-side — ``teams.organization_id`` on the team
store row — never in the Team document, so exports stay portable.

This module owns the ``organization`` table per the house pattern (each module registers its own
schema). Budgets are stored but not yet enforced — org budget checks land at C5; theme/priority
feed the portfolio surfaces from C1.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .db import Db, register_schema
from .ids import new_org_id

DEFAULT_ORG_KEY = "default"

SCHEMA = """
CREATE TABLE IF NOT EXISTS organization (
    id             TEXT PRIMARY KEY,
    key            TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    purpose        TEXT NOT NULL DEFAULT '',
    theme_json     TEXT NOT NULL DEFAULT '{}',
    priority_class TEXT NOT NULL DEFAULT 'batch',
    budget_json    TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT,
    updated_at     TEXT
);
"""
register_schema(SCHEMA)


class OrgError(Exception):
    pass


class OrgNotFound(OrgError):
    pass


class OrgNotEmpty(OrgError):
    pass


class Organization(BaseModel):
    """The umbrella entity (new sense; the chart unit is :class:`~canopy_server.models.Team`)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    key: str
    name: str
    purpose: str = ""
    theme: dict[str, Any] = Field(default_factory=dict)
    priorityClass: str = "batch"
    budget: dict[str, Any] = Field(default_factory=dict)
    createdAt: str | None = None
    updatedAt: str | None = None


_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def valid_org_key(key: str) -> bool:
    """Keys are stable kebab-case slugs — they appear in filesystem paths and audit rows."""
    return bool(_KEY_RE.match(key))


def _row_to_org(row) -> Organization:
    return Organization(
        id=row["id"],
        key=row["key"],
        name=row["name"],
        purpose=row["purpose"],
        theme=json.loads(row["theme_json"] or "{}"),
        priorityClass=row["priority_class"],
        budget=json.loads(row["budget_json"] or "{}"),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


class OrgStore:
    """CRUD over the ``organization`` table. Deleting requires the org to be empty of teams —
    the caller (routes) checks membership via the team store; this class only stores."""

    def __init__(self, db: Db, *, now):
        self.db = db
        self._now = now

    def create(
        self,
        *,
        key: str,
        name: str,
        purpose: str = "",
        theme: dict[str, Any] | None = None,
        priority_class: str = "batch",
        budget: dict[str, Any] | None = None,
    ) -> Organization:
        if not valid_org_key(key):
            raise OrgError(f"Invalid organization key: {key!r} (kebab-case slug required)")
        ts = self._now()
        org = Organization(
            id=new_org_id(),
            key=key,
            name=name,
            purpose=purpose,
            theme=theme or {},
            priorityClass=priority_class,
            budget=budget or {},
            createdAt=ts,
            updatedAt=ts,
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO organization (id, key, name, purpose, theme_json, priority_class,"
                " budget_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    org.id,
                    org.key,
                    org.name,
                    org.purpose,
                    json.dumps(org.theme),
                    org.priorityClass,
                    json.dumps(org.budget),
                    ts,
                    ts,
                ),
            )
        return org

    def get(self, org_id: str) -> Organization:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM organization WHERE id = ?", (org_id,)).fetchone()
        if row is None:
            raise OrgNotFound(org_id)
        return _row_to_org(row)

    def get_by_key(self, key: str) -> Organization | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM organization WHERE key = ?", (key,)).fetchone()
        return _row_to_org(row) if row is not None else None

    def list(self) -> list[Organization]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM organization ORDER BY created_at, key").fetchall()
        return [_row_to_org(r) for r in rows]

    def update(
        self,
        org_id: str,
        *,
        name: str | None = None,
        purpose: str | None = None,
        theme: dict[str, Any] | None = None,
        priority_class: str | None = None,
        budget: dict[str, Any] | None = None,
    ) -> Organization:
        org = self.get(org_id)  # raises OrgNotFound; `key` is immutable by omission
        fields = {
            "name": name if name is not None else org.name,
            "purpose": purpose if purpose is not None else org.purpose,
            "theme_json": json.dumps(theme if theme is not None else org.theme),
            "priority_class": priority_class if priority_class is not None else org.priorityClass,
            "budget_json": json.dumps(budget if budget is not None else org.budget),
            "updated_at": self._now(),
        }
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE organization SET name=?, purpose=?, theme_json=?, priority_class=?,"
                " budget_json=?, updated_at=? WHERE id=?",
                (*fields.values(), org_id),
            )
        return self.get(org_id)

    def delete(self, org_id: str) -> None:
        org = self.get(org_id)
        if org.key == DEFAULT_ORG_KEY:
            raise OrgError("The default organization cannot be deleted.")
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM organization WHERE id = ?", (org_id,))


def ensure_default_org(db: Db, *, now) -> str:
    """Create the ``default`` Organization if absent; return its id (boot migration, 07 §2.3)."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM organization WHERE key = ?", (DEFAULT_ORG_KEY,)
        ).fetchone()
    if row is not None:
        return row["id"]
    store = OrgStore(db, now=now)
    org = store.create(
        key=DEFAULT_ORG_KEY,
        name="Default",
        purpose="Every team lives somewhere; this is where existing teams landed at migration.",
        theme={"color": "sage", "icon": "tree"},
    )
    return org.id


# --------------------------------------------------------------------------- #
# Filesystem regrouping (design/organizations/07 §2.5, milestone C1)
# --------------------------------------------------------------------------- #
def team_home_resolver(data_dir, db: Db):
    """Return ``team_id -> Path`` mapping a team to ``data/orgs/<orgKey>/teams/<teamId>``.

    The org key comes from live membership (falling back to ``default``), so the separation
    is visible in a directory listing (01 §7). Move-team relocates the tree (custody
    transfer); actuation is blocked during a move, so `claude --resume` continuity (F13)
    is preserved — the path changes only when the operator moves the team, never per
    actuation.
    """
    from pathlib import Path

    root = Path(data_dir) / "orgs"

    def resolve(team_id: str):
        with db.connect() as conn:
            row = conn.execute(
                "SELECT o.key AS key FROM teams t JOIN organization o"
                " ON o.id = t.organization_id WHERE t.id = ?",
                (team_id,),
            ).fetchone()
        key = row["key"] if row is not None else DEFAULT_ORG_KEY
        return root / key / "teams" / team_id

    return resolve


def migrate_c1_filesystem(data_dir, db: Db) -> None:
    """One-shot boot move (07 §2.5): ``data/work/<teamId>`` → ``<team-home>/work`` and
    ``data/repos/<teamId>`` → ``<team-home>/repos``. Idempotent — a moved tree no longer
    exists at the old path. Sandboxes stay at ``data/sandboxes`` (ephemeral, actuation-
    keyed); log homes already ride the work home (F16).
    """
    import shutil
    from pathlib import Path

    data = Path(data_dir)
    resolve = team_home_resolver(data, db)
    for kind in ("work", "repos"):
        legacy_root = data / kind
        if not legacy_root.is_dir():
            continue
        for entry in list(legacy_root.iterdir()):
            if not entry.is_dir():
                continue
            target = resolve(entry.name) / kind
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(target))
