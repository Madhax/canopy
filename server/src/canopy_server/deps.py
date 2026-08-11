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
from .sqlite_store import SqliteTeamStore
from .store import JsonFileStore


@lru_cache(maxsize=8)
def _db_for(path_str: str) -> Db:
    return Db(Path(path_str))


def get_db() -> Db:
    """The SQLite handle for the current data dir (schema ensured on first construction)."""
    return _db_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _sqlite_store_for(path_str: str, json_dir_str: str) -> SqliteTeamStore:
    return SqliteTeamStore(_db_for(path_str), migrate_from=Path(json_dir_str))


@lru_cache(maxsize=8)
def _json_store_for(path_str: str) -> JsonFileStore:
    return JsonFileStore(Path(path_str))


def get_store() -> SqliteTeamStore | JsonFileStore:
    """The team document store selected by ``[db] backend`` in canopy.toml."""
    if get_db_backend() == "sqlite":
        # migrate_from stays the legacy phase-1 JSON location (kept on disk as backup).
        return _sqlite_store_for(str(get_db_path()), str(get_data_dir() / "organizations"))
    return _json_store_for(str(get_data_dir()))


@lru_cache(maxsize=8)
def _org_store_for(path_str: str):
    from .orgs import OrgStore

    return OrgStore(_db_for(path_str), now=now_iso)


def get_org_store():
    """The Organization entity store (design/organizations/01; C1)."""
    return _org_store_for(str(get_db_path()))


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
def _connector_store_for(path_str: str):
    from .connectors import ConnectorStore

    return ConnectorStore(_db_for(path_str))


def get_connector_store():
    return _connector_store_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _github_client_for(path_str: str):
    from .github_client import GitHubClient

    return GitHubClient()


def get_github_client():
    """The GitHub REST client (builder-connectors.md §6). Tests override this dependency
    with a client wired to the in-memory transport — CI never touches the network."""
    return _github_client_for(str(get_db_path()))


def _connector_repo_source(path_str: str, data_dir_str: str):
    """team_id -> repo source: connector instance serving the repo family (an https URL for
    github, a local path for local-git) → F8 binding → None (boot [repo] source / fixture)."""
    from .catalog import get_catalog

    connectors = _connector_store_for(path_str)
    profiles = _profile_store_for(path_str)

    def resolve(team_id: str):
        binding = connectors.resolve(get_catalog(), team_id, None, "repo.read")
        if binding is not None:
            if binding.instance.packKey == "github":
                cfg = binding.instance.config
                return f"https://github.com/{cfg.get('owner')}/{cfg.get('repo')}.git"
            if binding.instance.packKey == "local-git":
                return binding.instance.config.get("source")
        return profiles.get_repo_source(team_id)

    return resolve


def _connector_repo_auth(path_str: str, data_dir_str: str):
    """team_id -> token for URL sources — revealed inside the control-plane process at call
    time only (invariant 10); never stored on the RepoManager or on disk."""
    from .catalog import get_catalog

    connectors = _connector_store_for(path_str)
    secrets = _secret_store_for(path_str, data_dir_str)

    def resolve(team_id: str):
        binding = connectors.resolve(get_catalog(), team_id, None, "repo.read")
        if binding is None:
            return None
        sid = binding.instance.secretBindings.get("scm-token")
        return secrets.reveal(sid) if sid else None

    return resolve


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
    from .config import get_prices
    from .engine.engine import ExecutionEngine

    repos = _repos_for(data_dir_str, _repo_source_str(), path_str)
    return ExecutionEngine(
        _work_store_for(path_str),
        _ledger_for(path_str),
        _artifact_store_for(path_str, data_dir_str),
        get_store(),
        activity=_activity_for(path_str),
        bus=_bus_for(path_str),  # dispatch/resume wake-ups ride the A3 delivery workers (E3)
        executors={  # governed actions (E4): consented via ApprovalGate, then executed here
            "repo-merge": lambda p: repos.merge(p["teamId"], p["branch"]),
            # The O2 step-1 executor (builder-connectors.md §5): push the work branch to the
            # team's GitHub instance and open the PR — only ever reached through an approved
            # ApprovalGate; the deny path leaves nothing outside the machine.
            "pr-create": _pr_create_executor(path_str, data_dir_str),
        },
        prices=get_prices(),  # settle-path cost estimation (F1) — same table the gateway holds
    )


def _pr_create_executor(path_str: str, data_dir_str: str):
    from .catalog import get_catalog

    def execute(p: dict) -> dict:
        team_id = p["teamId"]
        repos = _repos_for(data_dir_str, _repo_source_str(), path_str)
        pushed = repos.push_branch(team_id, p["branch"])
        binding = _connector_store_for(path_str).resolve(
            get_catalog(), team_id, None, "connector.github.pr.create"
        )
        if binding is None:
            # Local-git round: the push IS the deliverable; the PR is the operator's.
            return {**pushed, "prUrl": None}
        cfg = binding.instance.config
        token = _connector_repo_auth(path_str, data_dir_str)(team_id) or ""
        pr = _github_client_for(path_str).create_pr(
            token, cfg.get("owner", ""), cfg.get("repo", ""),
            title=p.get("title", pushed["branch"]), body=p.get("body", ""),
            head=pushed["branch"], base=cfg.get("targetBranch", "main"),
        )
        return {**pushed, "prUrl": pr.get("html_url"), "prNumber": pr.get("number")}

    return execute


def _repo_source_str() -> str:
    from .config import get_repo_source

    source = get_repo_source()
    return str(source) if source else ""


@lru_cache(maxsize=8)
def _repos_for(data_dir_str: str, source_str: str, path_str: str):
    from .orgs import team_home_resolver
    from .repos import RepoManager

    return RepoManager(
        Path(data_dir_str) / "repos",
        source=Path(source_str) if source_str else None,
        home_resolver=team_home_resolver(Path(data_dir_str), _db_for(path_str)),
        # Connector instance (live DB read) outranks the F8 binding outranks the boot-time
        # [repo] source — all mutable at runtime, no restart (builder-connectors.md §4).
        source_resolver=_connector_repo_source(path_str, data_dir_str),
        auth_resolver=_connector_repo_auth(path_str, data_dir_str),
    )


def get_repos():
    return _repos_for(str(get_data_dir()), _repo_source_str(), str(get_db_path()))


def get_engine():
    return _engine_for(str(get_db_path()), str(get_data_dir()))


@lru_cache(maxsize=8)
def _cadence_scheduler_for(path_str: str, data_dir_str: str):
    from .engine.cadence import CadenceScheduler

    return CadenceScheduler(
        _work_store_for(path_str),
        _engine_for(path_str, data_dir_str),
        _actuator_for(path_str, data_dir_str),
        activity=_activity_for(path_str),
    )


def get_cadence_scheduler():
    return _cadence_scheduler_for(str(get_db_path()), str(get_data_dir()))


@lru_cache(maxsize=8)
def _trigger_scheduler_for(path_str: str, data_dir_str: str):
    from .catalog import get_catalog
    from .engine.triggers import TriggerScheduler

    return TriggerScheduler(
        _work_store_for(path_str),
        _engine_for(path_str, data_dir_str),
        _actuator_for(path_str, data_dir_str),
        _connector_store_for(path_str),
        _secret_store_for(path_str, data_dir_str),
        _github_client_for(path_str),
        get_catalog(),
        activity=_activity_for(path_str),
    )


def get_trigger_scheduler():
    return _trigger_scheduler_for(str(get_db_path()), str(get_data_dir()))


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
        work_root=Path(data_dir_str) / "work",
        router=_router_for(path_str),
        home_resolver=_team_home_for(path_str, data_dir_str),
    )


@lru_cache(maxsize=8)
def _team_home_for(path_str: str, data_dir_str: str):
    from .orgs import team_home_resolver

    return team_home_resolver(Path(data_dir_str), _db_for(path_str))


def get_actuator():
    return _actuator_for(str(get_db_path()), str(get_data_dir()))


# --------------------------------------------------------------------------- #
# Capacity layer (design/organizations/02–03, C2). Cached per database file.
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=8)
def _provider_accounts_for(path_str: str):
    from .capacity.accounts import ProviderAccountStore

    return ProviderAccountStore(_db_for(path_str), now=now_iso)


def get_provider_accounts():
    return _provider_accounts_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _capacity_ledger_for(path_str: str):
    from .capacity.ledger import CapacityLedger
    from .config import get_capacity_attribution_window_s, get_capacity_reading_ttl_s

    return CapacityLedger(
        _db_for(path_str), now=now_iso,
        reading_ttl_s=get_capacity_reading_ttl_s(),
        attribution_window_s=get_capacity_attribution_window_s(),
    )


def get_capacity_ledger():
    return _capacity_ledger_for(str(get_db_path()))


@lru_cache(maxsize=8)
def _capacity_service_for(path_str: str):
    from .capacity.service import CapacityService
    from .config import get_capacity_enabled

    work_store = _work_store_for(path_str)

    def notify(team_id, severity, kind, text, *, dedupe_key=None):
        work_store.notify(team_id, severity, kind, text, dedupe_key=dedupe_key)

    return CapacityService(
        _provider_accounts_for(path_str), _capacity_ledger_for(path_str),
        _profile_store_for(path_str), enabled=get_capacity_enabled, notify=notify,
    )


def get_capacity_service():
    return _capacity_service_for(str(get_db_path()))
