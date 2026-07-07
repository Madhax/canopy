"""Agent Profiles & Bindings — the AI configuration per node (agent-profile.md).

An **Agent Profile** answers "which brain does this node get": provider, model, endpoint, key
reference, params. A **Binding** attaches a profile to a chart node. Both are deliberately kept
*out of the Organization document* (org-chart-editor.md §10) — the chart stays portable structure;
profiles carry machine-local, secret-adjacent detail — so they live here in the control plane as
their own records, org-scoped.

``provider`` is a closed enum. The design named ``anthropic`` and ``gemini``; we add ``mock`` as a
first-class member because the deterministic mock provider is the testing/demo spine (risk IM-2) —
a profile can point a node at ``mock`` and actuate with zero keys and zero spend.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .db import Db, register_schema
from .deps import now_iso
from .ids import new_binding_id, new_profile_id

Provider = Literal["anthropic", "gemini", "mock"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles_profile (
    id                 TEXT PRIMARY KEY,
    organization_id    TEXT NOT NULL,
    name               TEXT NOT NULL,
    provider           TEXT NOT NULL,
    model              TEXT NOT NULL,
    endpoint           TEXT,
    api_key_secret_id  TEXT,
    params             TEXT NOT NULL,
    system_preamble    TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_profiles_org ON profiles_profile (organization_id);

CREATE TABLE IF NOT EXISTS profiles_binding (
    id               TEXT PRIMARY KEY,
    organization_id  TEXT NOT NULL,
    agent_node_id    TEXT NOT NULL,
    org_path         TEXT NOT NULL DEFAULT '[]',
    profile_id       TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_binding_node
    ON profiles_binding (organization_id, agent_node_id, org_path);
CREATE INDEX IF NOT EXISTS ix_binding_org ON profiles_binding (organization_id);
"""
register_schema(SCHEMA)


class ProfileParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    maxOutputTokens: int = 4096
    temperature: float = 0.7
    providerOptions: dict[str, Any] = Field(default_factory=dict)


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    organizationId: str
    name: str
    provider: Provider
    model: str
    endpoint: str | None = None
    apiKeySecretId: str | None = None  # reference into the Secret Store — NEVER the key itself
    params: ProfileParams = Field(default_factory=ProfileParams)
    systemPreamble: str = ""
    createdAt: str
    updatedAt: str


class AgentBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    organizationId: str
    agentNodeId: str
    orgPath: list[str] = Field(default_factory=list)
    profileId: str


class ProfileStore:
    def __init__(self, db: Db):
        self.db = db

    # -- profiles ----------------------------------------------------------- #
    def _row_to_profile(self, row) -> AgentProfile:
        return AgentProfile(
            id=row["id"],
            organizationId=row["organization_id"],
            name=row["name"],
            provider=row["provider"],
            model=row["model"],
            endpoint=row["endpoint"],
            apiKeySecretId=row["api_key_secret_id"],
            params=ProfileParams.model_validate(json.loads(row["params"])),
            systemPreamble=row["system_preamble"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    def create_profile(
        self,
        org_id: str,
        *,
        name: str,
        provider: Provider,
        model: str,
        endpoint: str | None = None,
        api_key_secret_id: str | None = None,
        params: ProfileParams | None = None,
        system_preamble: str = "",
    ) -> AgentProfile:
        pid = new_profile_id()
        ts = now_iso()
        p = AgentProfile(
            id=pid,
            organizationId=org_id,
            name=name,
            provider=provider,
            model=model,
            endpoint=endpoint,
            apiKeySecretId=api_key_secret_id,
            params=params or ProfileParams(),
            systemPreamble=system_preamble,
            createdAt=ts,
            updatedAt=ts,
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO profiles_profile (id, organization_id, name, provider, model, "
                "endpoint, api_key_secret_id, params, system_preamble, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p.id, org_id, p.name, p.provider, p.model, p.endpoint, p.apiKeySecretId,
                    p.params.model_dump_json(), p.systemPreamble, p.createdAt, p.updatedAt,
                ),
            )
        return p

    def update_profile(self, profile_id: str, changes: dict[str, Any]) -> AgentProfile | None:
        current = self.get_profile(profile_id)
        if current is None:
            return None
        merged = current.model_copy(update=changes)
        merged.updatedAt = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE profiles_profile SET name=?, provider=?, model=?, endpoint=?, "
                "api_key_secret_id=?, params=?, system_preamble=?, updated_at=? WHERE id=?",
                (
                    merged.name, merged.provider, merged.model, merged.endpoint,
                    merged.apiKeySecretId, merged.params.model_dump_json(), merged.systemPreamble,
                    merged.updatedAt, profile_id,
                ),
            )
        return merged

    def delete_profile(self, profile_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM profiles_profile WHERE id = ?", (profile_id,))
            return cur.rowcount > 0

    def get_profile(self, profile_id: str) -> AgentProfile | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles_profile WHERE id = ?", (profile_id,)
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def list_profiles(self, org_id: str) -> list[AgentProfile]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM profiles_profile WHERE organization_id = ? ORDER BY created_at",
                (org_id,),
            ).fetchall()
        return [self._row_to_profile(r) for r in rows]

    # -- bindings ----------------------------------------------------------- #
    def _row_to_binding(self, row) -> AgentBinding:
        return AgentBinding(
            id=row["id"],
            organizationId=row["organization_id"],
            agentNodeId=row["agent_node_id"],
            orgPath=json.loads(row["org_path"]),
            profileId=row["profile_id"],
        )

    def set_binding(
        self, org_id: str, agent_node_id: str, profile_id: str, org_path: list[str] | None = None
    ) -> AgentBinding:
        """Upsert the binding for one node (one profile per node)."""
        path_json = json.dumps(org_path or [])
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id FROM profiles_binding WHERE organization_id=? AND agent_node_id=? "
                "AND org_path=?",
                (org_id, agent_node_id, path_json),
            ).fetchone()
            if row:
                bid = row["id"]
                conn.execute(
                    "UPDATE profiles_binding SET profile_id=? WHERE id=?", (profile_id, bid)
                )
            else:
                bid = new_binding_id()
                conn.execute(
                    "INSERT INTO profiles_binding (id, organization_id, agent_node_id, org_path, "
                    "profile_id) VALUES (?, ?, ?, ?, ?)",
                    (bid, org_id, agent_node_id, path_json, profile_id),
                )
        return AgentBinding(
            id=bid,
            organizationId=org_id,
            agentNodeId=agent_node_id,
            orgPath=org_path or [],
            profileId=profile_id,
        )

    def delete_binding(
        self, org_id: str, agent_node_id: str, org_path: list[str] | None = None
    ) -> bool:
        path_json = json.dumps(org_path or [])
        with self.db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM profiles_binding WHERE organization_id=? AND agent_node_id=? "
                "AND org_path=?",
                (org_id, agent_node_id, path_json),
            )
            return cur.rowcount > 0

    def get_binding(self, binding_id: str) -> AgentBinding | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles_binding WHERE id = ?", (binding_id,)
            ).fetchone()
        return self._row_to_binding(row) if row else None

    def get_binding_for_node(
        self, org_id: str, agent_node_id: str, org_path: list[str] | None = None
    ) -> AgentBinding | None:
        path_json = json.dumps(org_path or [])
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles_binding WHERE organization_id=? AND agent_node_id=? "
                "AND org_path=?",
                (org_id, agent_node_id, path_json),
            ).fetchone()
        return self._row_to_binding(row) if row else None

    def list_bindings(self, org_id: str) -> list[AgentBinding]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM profiles_binding WHERE organization_id = ?", (org_id,)
            ).fetchall()
        return [self._row_to_binding(r) for r in rows]
