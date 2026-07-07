"""Shared FastAPI dependencies + small helpers.

Service singletons are cached per storage location (the SQLite file path / data dir) so the same
handle is reused across requests, while tests that point ``CANOPY_DATA_DIR`` at a fresh temp dir
transparently get their own isolated database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from .config import get_data_dir, get_db_backend, get_db_path
from .db import Db
from .sqlite_store import SqliteOrgStore
from .store import JsonFileStore


@lru_cache(maxsize=8)
def _db_for(path_str: str) -> Db:
    return Db(Path(path_str))


def get_db() -> Db:
    """The SQLite handle for the current data dir (schema ensured on first construction)."""
    return _db_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _sqlite_store_for(path_str: str, json_dir_str: str) -> SqliteOrgStore:
    return SqliteOrgStore(_db_for(path_str), migrate_from=Path(json_dir_str))


@lru_cache(maxsize=8)
def _json_store_for(path_str: str) -> JsonFileStore:
    return JsonFileStore(Path(path_str))


def get_store() -> SqliteOrgStore | JsonFileStore:
    """The organization document store selected by ``[db] backend`` in canopy.toml."""
    if get_db_backend() == "sqlite":
        return _sqlite_store_for(str(get_db_path()), str(get_data_dir() / "organizations"))
    return _json_store_for(str(get_data_dir()))


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# Phase-2 control-plane services. Cached per database file; each owns its tables.
# Imports are lazy (inside the functions) so these modules can `from .deps import now_iso`
# without an import cycle.
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=8)
def _secret_store_for(path_str: str, data_dir_str: str):
    from .secretstore import LocalEncryptedSecretStore

    return LocalEncryptedSecretStore(_db_for(path_str), Path(data_dir_str))


def get_secret_store():
    return _secret_store_for(str(get_db_path()), str(get_data_dir()))


@lru_cache(maxsize=8)
def _profile_store_for(path_str: str):
    from .profiles import ProfileStore

    return ProfileStore(_db_for(path_str))


def get_profile_store():
    return _profile_store_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _ledger_for(path_str: str):
    from .ledger import SqliteLedger

    return SqliteLedger(_db_for(path_str))


def get_ledger():
    return _ledger_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _runtokens_for(path_str: str):
    from .runtokens import RunTokenStore

    return RunTokenStore(_db_for(path_str))


def get_runtokens():
    return _runtokens_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _activity_for(path_str: str):
    from .activity import ActivityLog

    return ActivityLog(_db_for(path_str))


def get_activity():
    return _activity_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _gateway_for(path_str: str, data_dir_str: str):
    from .config import get_prices, get_provider_concurrency
    from .gateway import DefaultModelGateway

    return DefaultModelGateway(
        _db_for(path_str),
        _profile_store_for(path_str),
        _secret_store_for(path_str, data_dir_str),
        _ledger_for(path_str),
        _runtokens_for(path_str),
        _activity_for(path_str),
        prices=get_prices(),
        concurrency=get_provider_concurrency(),
    )


def get_gateway():
    return _gateway_for(str(get_db_path()), str(get_data_dir()))
