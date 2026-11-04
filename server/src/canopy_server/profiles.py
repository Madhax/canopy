"""Agent Profiles & Bindings — the AI configuration per node (agent-profile.md).

An **Agent Profile** answers "which brain does this node get": provider, model, endpoint, key
reference, params. A **Binding** attaches a profile to a chart node. Both are deliberately kept
*out of the Team document* (org-chart-editor.md §10) — the chart stays portable structure;
profiles carry machine-local, secret-adjacent detail — so they live here in the control plane as
their own records, team-scoped.

``provider`` is a closed enum. The design named ``anthropic`` and ``gemini``; we add ``mock`` as a
first-class member because the deterministic mock provider is the testing/demo spine (risk IM-2) —
a profile can point a node at ``mock`` and actuate with zero keys and zero spend.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from .db import Db, register_schema
from .deps import now_iso
from .ids import new_binding_id, new_profile_id

Provider = Literal["anthropic", "gemini", "mock"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles_profile (
    id                  TEXT PRIMARY KEY,
    team_id             TEXT NOT NULL,
    name                TEXT NOT NULL,
    provider            TEXT NOT NULL,
    model               TEXT NOT NULL,
    endpoint            TEXT,
    api_key_secret_id   TEXT,
    provider_account_id TEXT,
    params              TEXT NOT NULL,
    system_preamble     TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_profiles_org ON profiles_profile (team_id);

CREATE TABLE IF NOT EXISTS profiles_binding (
    id               TEXT PRIMARY KEY,
    team_id  TEXT NOT NULL,
    agent_node_id    TEXT NOT NULL,
    team_path         TEXT NOT NULL DEFAULT '[]',
    profile_id       TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_binding_node
    ON profiles_binding (team_id, agent_node_id, team_path);
CREATE INDEX IF NOT EXISTS ix_binding_org ON profiles_binding (team_id);

-- The team-default profile (UX-35, docs/design/ux/04-first-run.md §4): the profile every node
-- of the team runs on unless a per-node binding overrides it. Control-plane data like bindings —
-- never part of the Team document. A dangling profile_id reads as "no default".
CREATE TABLE IF NOT EXISTS profiles_team_default (
    team_id     TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- F8: the team's work-target repo binding (operator data, mutable at runtime, no restart).
-- NULL/absent falls back to the boot-time [repo] source, then the fixture.
CREATE TABLE IF NOT EXISTS team_repo_source (
    team_id TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
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
    teamId: str
    name: str
    provider: Provider
    model: str
    endpoint: str | None = None
    apiKeySecretId: str | None = None  # reference into the Secret Store — NEVER the key itself
    # C2 (design/organizations/02 §2): auth lives on the ProviderAccount; the profile keeps
    # model choice. Nullable until the boot migration stamps it; legacy fields stay readable.
    providerAccountId: str | None = None
    params: ProfileParams = Field(default_factory=ProfileParams)
    systemPreamble: str = ""
    createdAt: str
    updatedAt: str


class AgentBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    teamId: str
    agentNodeId: str
    teamPath: list[str] = Field(default_factory=list)
    profileId: str


# The id a synthetic binding carries when a node inherits the team default (no per-node row).
TEAM_DEFAULT_BINDING_ID = "team-default"

# Fallback model per provider when canopy.toml's [prices.<provider>] table names none.
_FALLBACK_MODEL: dict[str, str] = {
    "mock": "mock-1",
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-2.5-flash",
}


def default_provider_and_model() -> tuple[str, str]:
    """The provider/model a freshly materialized team-default profile uses: the configured
    ``[gateway] default_provider`` (``mock`` out of the box — zero keys, zero spend) and the
    first model its price table lists."""
    from .config import get_default_provider, get_prices

    provider = get_default_provider()
    if provider not in _FALLBACK_MODEL:
        provider = "mock"
    priced = list((get_prices().get(provider) or {}).keys())
    return provider, (priced[0] if priced else _FALLBACK_MODEL[provider])


class ProfileStore:
    def __init__(self, db: Db):
        self.db = db

    # -- profiles ----------------------------------------------------------- #
    def _row_to_profile(self, row) -> AgentProfile:
        return AgentProfile(
            id=row["id"],
            teamId=row["team_id"],
            name=row["name"],
            provider=row["provider"],
            model=row["model"],
            endpoint=row["endpoint"],
            apiKeySecretId=row["api_key_secret_id"],
            providerAccountId=(row["provider_account_id"]
                               if "provider_account_id" in row.keys() else None),
            params=ProfileParams.model_validate(json.loads(row["params"])),
            systemPreamble=row["system_preamble"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    def create_profile(
        self,
        team_id: str,
        *,
        name: str,
        provider: Provider,
        model: str,
        endpoint: str | None = None,
        api_key_secret_id: str | None = None,
        provider_account_id: str | None = None,
        params: ProfileParams | None = None,
        system_preamble: str = "",
    ) -> AgentProfile:
        pid = new_profile_id()
        ts = now_iso()
        p = AgentProfile(
            id=pid,
            teamId=team_id,
            name=name,
            provider=provider,
            model=model,
            endpoint=endpoint,
            apiKeySecretId=api_key_secret_id,
            providerAccountId=provider_account_id,
            params=params or ProfileParams(),
            systemPreamble=system_preamble,
            createdAt=ts,
            updatedAt=ts,
        )
        with self.db.transaction() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(profiles_profile)")}
            if "provider_account_id" not in cols:
                conn.execute(
                    "ALTER TABLE profiles_profile ADD COLUMN provider_account_id TEXT"
                )
            conn.execute(
                "INSERT INTO profiles_profile (id, team_id, name, provider, model, "
                "endpoint, api_key_secret_id, provider_account_id, params, system_preamble, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p.id, team_id, p.name, p.provider, p.model, p.endpoint, p.apiKeySecretId,
                    p.providerAccountId, p.params.model_dump_json(), p.systemPreamble,
                    p.createdAt, p.updatedAt,
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
            cols = {r[1] for r in conn.execute("PRAGMA table_info(profiles_profile)")}
            if "provider_account_id" not in cols:
                conn.execute(
                    "ALTER TABLE profiles_profile ADD COLUMN provider_account_id TEXT"
                )
            conn.execute(
                "UPDATE profiles_profile SET name=?, provider=?, model=?, endpoint=?, "
                "api_key_secret_id=?, provider_account_id=?, params=?, system_preamble=?, "
                "updated_at=? WHERE id=?",
                (
                    merged.name, merged.provider, merged.model, merged.endpoint,
                    merged.apiKeySecretId, merged.providerAccountId,
                    merged.params.model_dump_json(), merged.systemPreamble,
                    merged.updatedAt, profile_id,
                ),
            )
        return merged

    def delete_profile(self, profile_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM profiles_profile WHERE id = ?", (profile_id,))
            conn.execute("DELETE FROM profiles_team_default WHERE profile_id = ?", (profile_id,))
            return cur.rowcount > 0

    def get_profile(self, profile_id: str) -> AgentProfile | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles_profile WHERE id = ?", (profile_id,)
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def list_profiles(self, team_id: str) -> list[AgentProfile]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM profiles_profile WHERE team_id = ? ORDER BY created_at",
                (team_id,),
            ).fetchall()
        return [self._row_to_profile(r) for r in rows]

    # -- bindings ----------------------------------------------------------- #
    def _row_to_binding(self, row) -> AgentBinding:
        return AgentBinding(
            id=row["id"],
            teamId=row["team_id"],
            agentNodeId=row["agent_node_id"],
            teamPath=json.loads(row["team_path"]),
            profileId=row["profile_id"],
        )

    def set_binding(
        self, team_id: str, agent_node_id: str, profile_id: str, team_path: list[str] | None = None
    ) -> AgentBinding:
        """Upsert the binding for one node (one profile per node)."""
        path_json = json.dumps(team_path or [])
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id FROM profiles_binding WHERE team_id=? AND agent_node_id=? "
                "AND team_path=?",
                (team_id, agent_node_id, path_json),
            ).fetchone()
            if row:
                bid = row["id"]
                conn.execute(
                    "UPDATE profiles_binding SET profile_id=? WHERE id=?", (profile_id, bid)
                )
            else:
                bid = new_binding_id()
                conn.execute(
                    "INSERT INTO profiles_binding (id, team_id, agent_node_id, team_path, "
                    "profile_id) VALUES (?, ?, ?, ?, ?)",
                    (bid, team_id, agent_node_id, path_json, profile_id),
                )
        return AgentBinding(
            id=bid,
            teamId=team_id,
            agentNodeId=agent_node_id,
            teamPath=team_path or [],
            profileId=profile_id,
        )

    def delete_binding(
        self, team_id: str, agent_node_id: str, team_path: list[str] | None = None
    ) -> bool:
        path_json = json.dumps(team_path or [])
        with self.db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM profiles_binding WHERE team_id=? AND agent_node_id=? "
                "AND team_path=?",
                (team_id, agent_node_id, path_json),
            )
            return cur.rowcount > 0

    def get_binding(self, binding_id: str) -> AgentBinding | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles_binding WHERE id = ?", (binding_id,)
            ).fetchone()
        return self._row_to_binding(row) if row else None

    def get_binding_for_node(
        self, team_id: str, agent_node_id: str, team_path: list[str] | None = None
    ) -> AgentBinding | None:
        path_json = json.dumps(team_path or [])
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles_binding WHERE team_id=? AND agent_node_id=? "
                "AND team_path=?",
                (team_id, agent_node_id, path_json),
            ).fetchone()
        return self._row_to_binding(row) if row else None

    def list_bindings(self, team_id: str) -> list[AgentBinding]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM profiles_binding WHERE team_id = ?", (team_id,)
            ).fetchall()
        return [self._row_to_binding(r) for r in rows]

    def resolve_binding(
        self, team_id: str, agent_node_id: str, team_path: list[str] | None = None
    ) -> AgentBinding | None:
        """The binding that actually powers a node: its own binding if it has one, else the
        team default (a synthetic binding with id ``team-default``), else None.

        Every runtime consumer (readiness, provisioning, the gateway, capacity attribution, the
        inspector) resolves through here so "which model feeds this node" has one answer."""
        own = self.get_binding_for_node(team_id, agent_node_id, team_path)
        if own is not None:
            return own
        default_id = self.get_team_default(team_id)
        if default_id is None:
            return None
        return AgentBinding(
            id=TEAM_DEFAULT_BINDING_ID,
            teamId=team_id,
            agentNodeId=agent_node_id,
            teamPath=team_path or [],
            profileId=default_id,
        )

    # -- team default (UX-35) ---------------------------------------------- #
    def get_team_default(self, team_id: str) -> str | None:
        """The team-default profile id, or None (unset, or pointing at a deleted profile)."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT d.profile_id FROM profiles_team_default d "
                "JOIN profiles_profile p ON p.id = d.profile_id WHERE d.team_id = ?",
                (team_id,),
            ).fetchone()
        return row["profile_id"] if row else None

    def set_team_default(self, team_id: str, profile_id: str | None) -> None:
        with self.db.transaction() as conn:
            if profile_id:
                conn.execute(
                    "INSERT INTO profiles_team_default (team_id, profile_id, updated_at) "
                    "VALUES (?, ?, ?) ON CONFLICT(team_id) DO UPDATE SET "
                    "profile_id=excluded.profile_id, updated_at=excluded.updated_at",
                    (team_id, profile_id, now_iso()),
                )
            else:
                conn.execute("DELETE FROM profiles_team_default WHERE team_id = ?", (team_id,))

    def ensure_team_default(self, team_id: str) -> str | None:
        """Give a team that has *no profiles at all* a ready-to-actuate default: one profile on
        the configured default provider (mock out of the box), set as the team default.

        Idempotent, and deliberately narrow — a team that already has profiles but no default
        is left alone (choosing among the operator's own profiles is the operator's call).
        Returns the team-default profile id, or None when none is set."""
        current = self.get_team_default(team_id)
        if current is not None or self.list_profiles(team_id):
            return current
        provider, model = default_provider_and_model()
        p = self.create_profile(
            team_id, name=f"Team default ({model})", provider=cast(Provider, provider),
            model=model,
        )
        self.set_team_default(team_id, p.id)
        return p.id

    # -- repo source (F8) --------------------------------------------------- #
    def get_repo_source(self, team_id: str) -> str | None:
        """The team's work-target repo binding, or None to fall back to config/fixture."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT source FROM team_repo_source WHERE team_id = ?", (team_id,)
            ).fetchone()
        return row["source"] if row else None

    def set_repo_source(self, team_id: str, source: str | None) -> None:
        with self.db.transaction() as conn:
            if source:
                conn.execute(
                    "INSERT INTO team_repo_source (team_id, source, updated_at) "
                    "VALUES (?, ?, ?) ON CONFLICT(team_id) "
                    "DO UPDATE SET source=excluded.source, updated_at=excluded.updated_at",
                    (team_id, source, now_iso()),
                )
            else:
                conn.execute(
                    "DELETE FROM team_repo_source WHERE team_id = ?", (team_id,)
                )
