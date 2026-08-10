"""Connector instances — an team's bound external systems (docs/design/builder-connectors.md).

A **ConnectorInstance** is the governance series' noun promoted to a store (connectors/02 §2):
per-team operator data beside profiles and secrets, mutable at runtime, never catalog data and
never chart data. It binds a catalog **pack** (the declaration: grants, config schema, secret
kinds) to one concrete external system (one repo, one workspace), with:

- ``secretBindings`` — Secret Store *references* per credentialKind; plaintext never lands here.
- ``enabledGrants`` — the team-level capability mask; unchecked means unusable team-wide.
- ``nodeLinks`` — scope: ``None`` = linked to the team root (team-wide); a list = only those
  nodes; ``[]`` = configured but unlinked (inert, dimmed in the builder).

Resolution (``resolve``) answers the only question the rest of the platform asks: *for this
node, which instance serves this grant key, if any* — walking direct pack-grant keys and the
``provides`` aliases (connectors/01 §4), scope links, and the enablement mask. Precedence:
node-linked outranks team-wide (the pin); ties break to the older instance, deterministically.
"""

from __future__ import annotations

import json
from typing import Any

from nanoid import generate
from pydantic import BaseModel, ConfigDict, Field

from .db import Db, register_schema
from .deps import now_iso
from .models import Catalog, ConnectorGrant, ConnectorPack

SCHEMA = """
CREATE TABLE IF NOT EXISTS connector_instance (
    id              TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    pack_key        TEXT NOT NULL,
    name            TEXT NOT NULL,
    config          TEXT NOT NULL,
    secret_bindings TEXT NOT NULL,
    enabled_grants  TEXT NOT NULL,
    node_links      TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_connector_org ON connector_instance (team_id);
"""
register_schema(SCHEMA)

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def new_instance_id() -> str:
    return "ci_" + generate(_ALPHABET, 10)


class ConnectorInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    teamId: str
    packKey: str
    name: str
    config: dict[str, str] = Field(default_factory=dict)
    secretBindings: dict[str, str] = Field(default_factory=dict)  # kind -> secretId, never value
    enabledGrants: list[str] = Field(default_factory=list)
    nodeLinks: list[str] | None = None  # None = team-wide; [] = unlinked/inert
    enabled: bool = True
    createdAt: str
    updatedAt: str


class Binding(BaseModel):
    """A resolved grant → instance binding (connectors/02 §5), params already folded."""

    model_config = ConfigDict(extra="forbid")
    grantKey: str
    servingGrant: ConnectorGrant
    instance: ConnectorInstance
    params: dict[str, Any] = Field(default_factory=dict)


class ConnectorStore:
    def __init__(self, db: Db):
        self.db = db

    # ------------------------------------------------------------------- CRUD
    def _row(self, row) -> ConnectorInstance:
        links = row["node_links"]
        return ConnectorInstance(
            id=row["id"], teamId=row["team_id"], packKey=row["pack_key"],
            name=row["name"], config=json.loads(row["config"]),
            secretBindings=json.loads(row["secret_bindings"]),
            enabledGrants=json.loads(row["enabled_grants"]),
            nodeLinks=json.loads(links) if links is not None else None,
            enabled=bool(row["enabled"]),
            createdAt=row["created_at"], updatedAt=row["updated_at"],
        )

    def create(
        self, team_id: str, pack_key: str, name: str, *,
        config: dict[str, str] | None = None,
        secret_bindings: dict[str, str] | None = None,
        enabled_grants: list[str] | None = None,
        node_links: list[str] | None = None,
    ) -> ConnectorInstance:
        ts = now_iso()
        inst = ConnectorInstance(
            id=new_instance_id(), teamId=team_id, packKey=pack_key, name=name,
            config=config or {}, secretBindings=secret_bindings or {},
            enabledGrants=enabled_grants or [], nodeLinks=node_links,
            createdAt=ts, updatedAt=ts,
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO connector_instance (id, team_id, pack_key, name, config, "
                "secret_bindings, enabled_grants, node_links, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (inst.id, team_id, pack_key, name, json.dumps(inst.config),
                 json.dumps(inst.secretBindings), json.dumps(inst.enabledGrants),
                 json.dumps(inst.nodeLinks) if inst.nodeLinks is not None else None,
                 1, ts, ts),
            )
        return inst

    def update(self, instance_id: str, changes: dict[str, Any]) -> ConnectorInstance | None:
        current = self.get(instance_id)
        if current is None:
            return None
        merged = current.model_copy(update=changes)
        merged.updatedAt = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE connector_instance SET name=?, config=?, secret_bindings=?, "
                "enabled_grants=?, node_links=?, enabled=?, updated_at=? WHERE id=?",
                (merged.name, json.dumps(merged.config), json.dumps(merged.secretBindings),
                 json.dumps(merged.enabledGrants),
                 json.dumps(merged.nodeLinks) if merged.nodeLinks is not None else None,
                 1 if merged.enabled else 0, merged.updatedAt, instance_id),
            )
        return merged

    def delete(self, instance_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM connector_instance WHERE id=?", (instance_id,))
            return cur.rowcount > 0

    def get(self, instance_id: str) -> ConnectorInstance | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM connector_instance WHERE id=?", (instance_id,)
            ).fetchone()
        return self._row(row) if row else None

    def list(self, team_id: str) -> list[ConnectorInstance]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM connector_instance WHERE team_id=? "
                "ORDER BY created_at, id",
                (team_id,),
            ).fetchall()
        return [self._row(r) for r in rows]

    # -------------------------------------------------------------- resolution
    def resolve(
        self, catalog: Catalog, team_id: str, node_id: str | None, grant_key: str,
    ) -> Binding | None:
        """The instance serving ``grant_key`` for ``node_id`` in this team, or None.

        ``node_id=None`` asks team-wide ("does anything serve this at all") — used by repo
        source resolution, where materialization happens per team, not per node.
        """
        packs = {p.key: p for p in catalog.connectorPacks}
        candidates: list[tuple[int, ConnectorInstance, ConnectorGrant]] = []
        for inst in self.list(team_id):
            if not inst.enabled:
                continue
            pack = packs.get(inst.packKey)
            if pack is None:
                continue
            serving = _serving_grant(pack, inst, grant_key)
            if serving is None:
                continue
            if inst.nodeLinks is None:
                rank = 0  # team-wide
            elif node_id is not None and node_id in inst.nodeLinks:
                rank = 1  # node pin outranks team-wide (connectors/02 §3)
            elif node_id is None and inst.nodeLinks:
                rank = 0  # team-level question: any linked instance counts
            else:
                continue  # scoped away from this node (or unlinked: [] matches nobody)
            candidates.append((rank, inst, serving))
        if not candidates:
            return None
        # Highest rank wins; ties break to the older instance (list() is created_at-ordered,
        # sort is stable) — deterministic, warned in readiness.
        rank, inst, serving = sorted(candidates, key=lambda c: -c[0])[0]
        params = {**serving.params}
        for k, v in inst.config.items():
            field = (packs[inst.packKey].configSchema or {}).get(k)
            if field is not None:
                params[k] = v
        return Binding(grantKey=grant_key, servingGrant=serving, instance=inst, params=params)

    def reachable(self, catalog: Catalog, team_id: str, node_id: str) -> list[ConnectorInstance]:
        """Instances this node can reach at all (team-wide or directly linked) — the builder's
        node chips and the MCP surface filter."""
        out = []
        for inst in self.list(team_id):
            if not inst.enabled:
                continue
            if inst.nodeLinks is None or node_id in inst.nodeLinks:
                out.append(inst)
        return out


def _serving_grant(
    pack: ConnectorPack, inst: ConnectorInstance, grant_key: str,
) -> ConnectorGrant | None:
    """The pack grant that serves ``grant_key`` through this instance, honoring the team mask:
    a direct namespaced match, or a ``provides`` alias (connectors/01 §4)."""
    for g in pack.grants:
        if g.key not in inst.enabledGrants:
            continue
        if g.key == grant_key or grant_key in g.provides:
            return g
    return None


def readiness_issues(
    catalog: Catalog, store: ConnectorStore, team_id: str, node_id: str,
    effective_grants: list[str],
) -> list[tuple[str, str]]:
    """Connector readiness for one node (connectors/02 §5): ``(code, detail)`` tuples.

    - CONNECTOR_UNBOUND: a connector-backed grant with no resolving instance. Abstract keys
      (repo.*) are exempt — they fall back to the F8/toml/fixture chain by design.
    - CONNECTOR_SECRET_UNBOUND: an instance resolves but a required credential is missing.
    - CONNECTOR_GRANT_DISABLED: the role grants a namespaced key an existing instance of the
      pack carries but the team mask excludes.
    """
    packs = {p.key: p for p in catalog.connectorPacks}
    issues: list[tuple[str, str]] = []
    for gk in effective_grants:
        if not gk.startswith("connector."):
            continue
        binding = store.resolve(catalog, team_id, node_id, gk)
        if binding is None:
            pack_key = gk.split(".", 2)[1]
            masked = any(
                i.packKey == pack_key and _pack_has_grant(packs.get(pack_key), gk)
                and gk not in i.enabledGrants
                for i in store.list(team_id)
            )
            code = "CONNECTOR_GRANT_DISABLED" if masked else "CONNECTOR_UNBOUND"
            issues.append((code, gk))
            continue
        pack = packs[binding.instance.packKey]
        for decl in pack.secrets:
            if decl.required and decl.credentialKind not in binding.instance.secretBindings:
                issues.append(("CONNECTOR_SECRET_UNBOUND", f"{gk}:{decl.credentialKind}"))
    return issues


def _pack_has_grant(pack: ConnectorPack | None, grant_key: str) -> bool:
    return pack is not None and any(g.key == grant_key for g in pack.grants)
