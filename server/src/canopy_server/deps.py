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
def _work_store_for(path_str: str):
    from .engine.store import WorkStore

    return WorkStore(_db_for(path_str))


def get_work_store():
    return _work_store_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _artifact_store_for(path_str: str, data_dir_str: str):
    from .artifacts import artifact_store_registry
    from .config import get_artifact_backend

    return artifact_store_registry.create(
        get_artifact_backend(), _db_for(path_str), Path(data_dir_str) / "artifacts"
    )


def get_artifact_store():
    return _artifact_store_for(str(get_db_path()), str(get_data_dir()))


def _assignment_meter_resolver(work_store):
    """Maps a gateway ``task_id`` (an assignment id) to that assignment's bound meter (D1). Returns
    None for unknown/foreign tasks so the gateway falls back to the node's default meter."""

    def resolve(actuation_id: str, node_id: str, task_id: str) -> str | None:
        a = work_store.get_assignment(task_id)
        if a is None or a.actuationId != actuation_id or a.nodeId != node_id:
            return None
        return a.meterId

    return resolve


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
        meter_resolver=_assignment_meter_resolver(_work_store_for(path_str)),
    )


def get_gateway():
    return _gateway_for(str(get_db_path()), str(get_data_dir()))


@lru_cache(maxsize=8)
def _engine_for(path_str: str, data_dir_str: str):
    from .engine.engine import ExecutionEngine

    return ExecutionEngine(
        _work_store_for(path_str),
        _ledger_for(path_str),
        _artifact_store_for(path_str, data_dir_str),
        get_store(),
        activity=_activity_for(path_str),
    )


def get_engine():
    return _engine_for(str(get_db_path()), str(get_data_dir()))


@lru_cache(maxsize=8)
def _directory_for(path_str: str):
    from .directory import AgentDirectory

    return AgentDirectory(_db_for(path_str))


def get_directory():
    return _directory_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _sandbox_for(path_str: str):
    from .config import get_sandbox_provider
    from .sandbox import sandbox_registry

    return sandbox_registry.create(get_sandbox_provider())


def get_sandbox():
    """The sandbox provider singleton — holds live process handles, so cached per process/db."""
    return _sandbox_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _bus_for(path_str: str):
    from .bus import bus_registry
    from .config import get_bus_backend

    return bus_registry.create(get_bus_backend(), _db_for(path_str))


def get_bus():
    return _bus_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _router_for(path_str: str):
    from .router import MessageRouter

    return MessageRouter(_db_for(path_str), _bus_for(path_str))


def get_router():
    return _router_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _actuator_for(path_str: str, data_dir_str: str):
    from .actuator import Actuator
    from .catalog import get_catalog
    from .config import get_agent_pythonpath, get_boot_timeout_s, get_cp_url

    return Actuator(
        _db_for(path_str),
        get_store(),
        get_catalog(),
        _profile_store_for(path_str),
        _secret_store_for(path_str, data_dir_str),
        _ledger_for(path_str),
        _runtokens_for(path_str),
        _directory_for(path_str),
        _sandbox_for(path_str),
        _activity_for(path_str),
        cp_url=get_cp_url(),
        agent_pythonpath=get_agent_pythonpath(),
        boot_timeout_s=get_boot_timeout_s(),
        sandboxes_root=Path(data_dir_str) / "sandboxes",
        router=_router_for(path_str),
    )


def get_actuator():
    return _actuator_for(str(get_db_path()), str(get_data_dir()))
