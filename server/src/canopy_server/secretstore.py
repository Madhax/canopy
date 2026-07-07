"""Secret Store — encrypted-at-rest API keys (agent-profile.md §1, invariant 10).

Secrets are the credential material an Agent Profile references (``apiKeySecretId``) but never
contains. Two rules from the design are enforced here by construction:

* **Plaintext leaves this module in exactly one direction:** :meth:`SecretStore.reveal`, called
  only by the Model Gateway inside the control-plane process. No REST route returns it — the
  operator API is write-only (create / rotate / delete) and reads return metadata only.
* **Encrypted at rest.** ``LocalEncryptedSecretStore`` uses Fernet (AES-128-CBC + HMAC) with a
  master key in ``data/master.key`` (0600, generated on first run — "protect this file"). This is
  the trusted-local v1 posture (topology.md §5); OS keychain / Vault / IAM are roadmap swaps
  behind this same ABC, and IAM-based providers remove stored keys entirely.

Threat model for this posture is written down in ``docs/actuation/threat-model.md`` (risk AR-6).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from .config import get_data_dir
from .db import Db, register_schema
from .deps import now_iso
from .ids import new_secret_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS secrets_secret (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name            TEXT NOT NULL,
    ciphertext      BLOB NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_secrets_org ON secrets_secret (organization_id);
"""
register_schema(SCHEMA)


class SecretMeta(BaseModel):
    """Everything about a secret *except* its value — the only shape any API returns."""

    id: str
    organizationId: str
    name: str
    createdAt: str


class SecretStore(ABC):
    key: str

    @abstractmethod
    def create(self, org_id: str, name: str, plaintext: str) -> SecretMeta: ...

    @abstractmethod
    def rotate(self, secret_id: str, plaintext: str) -> SecretMeta | None: ...

    @abstractmethod
    def delete(self, secret_id: str) -> bool: ...

    @abstractmethod
    def list(self, org_id: str) -> list[SecretMeta]: ...

    @abstractmethod
    def get_meta(self, secret_id: str) -> SecretMeta | None: ...

    @abstractmethod
    def reveal(self, secret_id: str) -> str | None:
        """Plaintext — gateway-only. Never exposed through any REST route."""


def _load_or_create_master_key(data_dir: Path) -> bytes:
    from cryptography.fernet import Fernet

    key_path = data_dir / "master.key"
    if key_path.is_file():
        return key_path.read_bytes()
    data_dir.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    # Write 0600 where the OS honors it (POSIX); best-effort on Windows.
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


class LocalEncryptedSecretStore(SecretStore):
    key = "local-encrypted"

    def __init__(self, db: Db, data_dir: Path | None = None):
        from cryptography.fernet import Fernet

        self.db = db
        self._fernet = Fernet(_load_or_create_master_key(data_dir or get_data_dir()))

    def _row_to_meta(self, row) -> SecretMeta:
        return SecretMeta(
            id=row["id"],
            organizationId=row["organization_id"],
            name=row["name"],
            createdAt=row["created_at"],
        )

    def create(self, org_id: str, name: str, plaintext: str) -> SecretMeta:
        sid = new_secret_id()
        ts = now_iso()
        ct = self._fernet.encrypt(plaintext.encode("utf-8"))
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO secrets_secret (id, organization_id, name, ciphertext, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (sid, org_id, name, ct, ts),
            )
        return SecretMeta(id=sid, organizationId=org_id, name=name, createdAt=ts)

    def rotate(self, secret_id: str, plaintext: str) -> SecretMeta | None:
        ct = self._fernet.encrypt(plaintext.encode("utf-8"))
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE secrets_secret SET ciphertext = ? WHERE id = ?", (ct, secret_id)
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM secrets_secret WHERE id = ?", (secret_id,)
            ).fetchone()
        return self._row_to_meta(row)

    def delete(self, secret_id: str) -> bool:
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM secrets_secret WHERE id = ?", (secret_id,))
            return cur.rowcount > 0

    def list(self, org_id: str) -> list[SecretMeta]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM secrets_secret WHERE organization_id = ? ORDER BY created_at",
                (org_id,),
            ).fetchall()
        return [self._row_to_meta(r) for r in rows]

    def get_meta(self, secret_id: str) -> SecretMeta | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM secrets_secret WHERE id = ?", (secret_id,)
            ).fetchone()
        return self._row_to_meta(row) if row else None

    def reveal(self, secret_id: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT ciphertext FROM secrets_secret WHERE id = ?", (secret_id,)
            ).fetchone()
        if row is None:
            return None
        return self._fernet.decrypt(row["ciphertext"]).decode("utf-8")
