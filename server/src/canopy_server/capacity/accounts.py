"""ProviderAccounts — one authenticated identity at one provider (02-capacity-model §2).

Operator-level: a Claude Max login belongs to the human, not to any Organization —
organizations get *shares* of a pool, never copies of a login. Profiles slim to
model-choice and reference an account for auth (the §2.3 migration below is additive
and non-destructive: profile rows keep their legacy columns, gaining
``provider_account_id``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..db import Db, register_schema
from ..ids import new_provider_account_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_account (
    id                       TEXT PRIMARY KEY,
    provider                 TEXT NOT NULL,
    auth_mode                TEXT NOT NULL,          -- subscription-cli | api-key | mock
    label                    TEXT NOT NULL,
    cli_config_dir           TEXT,
    cli_cmd                  TEXT,
    api_key_secret_id        TEXT,
    plan_hint                TEXT,
    max_concurrent_sessions  INTEGER NOT NULL DEFAULT 4,
    extra_usage_cap_usd      REAL,
    created_at               TEXT
);
"""
register_schema(SCHEMA)


class ProviderAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    authMode: str
    label: str
    cliConfigDir: str | None = None
    cliCmd: str | None = None
    apiKeySecretId: str | None = None
    planHint: str | None = None
    maxConcurrentSessions: int = 4
    extraUsageCapUsd: float | None = None
    createdAt: str | None = None


def _row_to_account(row) -> ProviderAccount:
    return ProviderAccount(
        id=row["id"],
        provider=row["provider"],
        authMode=row["auth_mode"],
        label=row["label"],
        cliConfigDir=row["cli_config_dir"],
        cliCmd=row["cli_cmd"],
        apiKeySecretId=row["api_key_secret_id"],
        planHint=row["plan_hint"],
        maxConcurrentSessions=row["max_concurrent_sessions"],
        extraUsageCapUsd=row["extra_usage_cap_usd"],
        createdAt=row["created_at"],
    )


class ProviderAccountStore:
    """CRUD + the C2 boot migration. Construction is idempotent: it splits existing
    profile rows into accounts once (one per distinct ``(provider, api_key_secret_id)``,
    plus one ``subscription-cli`` account for the operator's CLI login) and stamps
    ``profiles_profile.provider_account_id``.
    """

    def __init__(self, db: Db, *, now):
        self.db = db
        db.ensure_schema()  # idempotent; direct construction (tests) predates route imports
        self._now = now
        self._migrate_profiles()

    # -- reads --------------------------------------------------------------- #
    def get(self, account_id: str) -> ProviderAccount | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM provider_account WHERE id = ?", (account_id,)
            ).fetchone()
        return _row_to_account(row) if row else None

    def list(self) -> list[ProviderAccount]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_account ORDER BY created_at, id"
            ).fetchall()
        return [_row_to_account(r) for r in rows]

    def find(self, provider: str, auth_mode: str,
             api_key_secret_id: str | None = None) -> ProviderAccount | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM provider_account WHERE provider=? AND auth_mode=?"
                " AND (api_key_secret_id IS ? OR api_key_secret_id = ?) LIMIT 1",
                (provider, auth_mode, api_key_secret_id, api_key_secret_id),
            ).fetchone()
        return _row_to_account(row) if row else None

    # -- writes -------------------------------------------------------------- #
    def create(self, *, provider: str, auth_mode: str, label: str,
               cli_config_dir: str | None = None, cli_cmd: str | None = None,
               api_key_secret_id: str | None = None, plan_hint: str | None = None,
               max_concurrent_sessions: int = 4,
               extra_usage_cap_usd: float | None = None) -> ProviderAccount:
        acct = ProviderAccount(
            id=new_provider_account_id(), provider=provider, authMode=auth_mode,
            label=label, cliConfigDir=cli_config_dir, cliCmd=cli_cmd,
            apiKeySecretId=api_key_secret_id, planHint=plan_hint,
            maxConcurrentSessions=max_concurrent_sessions,
            extraUsageCapUsd=extra_usage_cap_usd, createdAt=self._now(),
        )
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO provider_account (id, provider, auth_mode, label,"
                " cli_config_dir, cli_cmd, api_key_secret_id, plan_hint,"
                " max_concurrent_sessions, extra_usage_cap_usd, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (acct.id, acct.provider, acct.authMode, acct.label, acct.cliConfigDir,
                 acct.cliCmd, acct.apiKeySecretId, acct.planHint,
                 acct.maxConcurrentSessions, acct.extraUsageCapUsd, acct.createdAt),
            )
        return acct

    def ensure_cli_account(self, provider: str = "anthropic",
                           plan_hint: str | None = None) -> ProviderAccount:
        """The operator's CLI login as an account (02 §2): every install that runs
        ``cli-claude`` sessions has exactly one, discovered rather than configured."""
        existing = self.find(provider, "subscription-cli")
        if existing is not None:
            return existing
        return self.create(
            provider=provider, auth_mode="subscription-cli",
            label=f"{provider.title()} subscription (CLI)", plan_hint=plan_hint,
        )

    def ensure_mock_account(self) -> ProviderAccount:
        """CI's trivially-infinite account (02 §2)."""
        existing = self.find("mock", "mock")
        if existing is not None:
            return existing
        return self.create(provider="mock", auth_mode="mock", label="Mock (CI)")

    # -- the §2.3 boot migration --------------------------------------------- #
    def _migrate_profiles(self) -> None:
        with self.db.transaction() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(profiles_profile)")}
            if not cols:
                return  # profiles module not loaded in this process (standalone boot)
            if "provider_account_id" not in cols:
                conn.execute(
                    "ALTER TABLE profiles_profile ADD COLUMN provider_account_id TEXT"
                )
            rows = conn.execute(
                "SELECT DISTINCT provider, api_key_secret_id FROM profiles_profile"
                " WHERE provider_account_id IS NULL"
            ).fetchall()
        for r in rows:
            provider, secret = r["provider"], r["api_key_secret_id"]
            if provider == "mock":
                acct = self.ensure_mock_account()
            elif secret:
                acct = self.find(provider, "api-key", secret) or self.create(
                    provider=provider, auth_mode="api-key",
                    label=f"{provider.title()} api-key", api_key_secret_id=secret,
                )
            else:
                # Keyless non-mock profiles ride the operator's CLI login.
                acct = self.ensure_cli_account(provider)
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE profiles_profile SET provider_account_id = ?"
                    " WHERE provider = ? AND (api_key_secret_id IS ? OR"
                    " api_key_secret_id = ?) AND provider_account_id IS NULL",
                    (acct.id, provider, secret, secret),
                )
