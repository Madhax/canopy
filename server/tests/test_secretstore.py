"""Secret Store — encryption at rest + reveal-only-for-gateway (invariant 10)."""

from __future__ import annotations

from pathlib import Path

from canopy_server.db import Db
from canopy_server.secretstore import LocalEncryptedSecretStore


def _store(tmp_path: Path) -> LocalEncryptedSecretStore:
    return LocalEncryptedSecretStore(Db(tmp_path / "canopy.db"), tmp_path)


def test_roundtrip_and_rotate(tmp_path):
    store = _store(tmp_path)
    meta = store.create("o1", "anthropic", "sk-plaintext")
    assert store.reveal(meta.id) == "sk-plaintext"
    store.rotate(meta.id, "sk-rotated")
    assert store.reveal(meta.id) == "sk-rotated"
    assert store.delete(meta.id) is True
    assert store.reveal(meta.id) is None


def test_master_key_generated_once(tmp_path):
    _store(tmp_path)
    key_path = tmp_path / "master.key"
    assert key_path.is_file()
    first = key_path.read_bytes()
    _store(tmp_path)  # second construction reuses the same key
    assert key_path.read_bytes() == first


def test_ciphertext_at_rest_is_not_plaintext(tmp_path):
    store = _store(tmp_path)
    meta = store.create("o1", "k", "the-quick-brown-fox")
    with Db(tmp_path / "canopy.db").connect() as conn:
        row = conn.execute(
            "SELECT ciphertext FROM secrets_secret WHERE id = ?", (meta.id,)
        ).fetchone()
    assert b"the-quick-brown-fox" not in bytes(row["ciphertext"])
