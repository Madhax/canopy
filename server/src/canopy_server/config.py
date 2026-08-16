"""Runtime configuration: env-driven paths plus the ``canopy.toml`` implementation registry.

Phase 1 needed only a couple of env vars. Phase 2 adds ``canopy.toml`` (topology.md §3.5): the
file that selects implementations by key (db backend, sandbox provider, bus backend, default
model provider) and carries operator data — the model price table (kept as data, not code,
because it churns fastest — risk IM-4) and per-provider concurrency caps (risk SC-3).

Everything degrades to sane defaults when ``canopy.toml`` is absent, so a clean checkout still
boots. ``CANOPY_CONFIG`` overrides the file location; ``CANOPY_DATA_DIR`` the data location.
"""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

# repo_root/server/src/canopy_server/config.py -> repo_root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def get_port() -> int:
    return int(os.environ.get("CANOPY_PORT", "8700"))


def get_data_dir() -> Path:
    raw = os.environ.get("CANOPY_DATA_DIR")
    return Path(raw) if raw else _REPO_ROOT / "data"


def get_ui_dist() -> Path:
    """Built UI to serve in production (``pnpm build`` output)."""
    return _REPO_ROOT / "ui" / "dist"


def get_cp_url() -> str:
    """The control-plane base URL agents call (charter/register/heartbeat/gateway)."""
    return os.environ.get("CANOPY_CP_URL", f"http://127.0.0.1:{get_port()}")


def get_agent_pythonpath() -> str:
    """Dev affordance: the ``canopy-agent`` source dir, so ``python -m canopy_agent`` resolves in a
    subprocess without a formal install. Empty when packaged (canopy-agent pip-installed)."""
    src = _REPO_ROOT / "agent" / "src"
    return str(src) if src.is_dir() else ""


def get_boot_timeout_s() -> int:
    return int(os.environ.get("CANOPY_BOOT_TIMEOUT", "30"))


# --------------------------------------------------------------------------- #
# canopy.toml
# --------------------------------------------------------------------------- #
_DEFAULTS: dict[str, Any] = {
    "db": {"backend": "sqlite", "path": "canopy.db"},
    "sandbox": {"provider": "subprocess"},
    "bus": {"backend": "sqlite"},
    "artifacts": {"backend": "local"},
    "secrets": {"backend": "local-encrypted"},
    "gateway": {
        "default_provider": "mock",
        "concurrency": {"anthropic": 4, "gemini": 4, "mock": 64},
    },
    "work": {"rework_grant_pct": 20, "stall_minutes": 10, "stall_none_steps": 5},
    "repo": {"source": ""},
    "execution": {"allow_trusted_local": False, "runtime_override": ""},
    "prices": {},
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _config_path() -> Path | None:
    raw = os.environ.get("CANOPY_CONFIG")
    if raw:
        p = Path(raw)
        return p if p.is_file() else None
    candidate = _REPO_ROOT / "canopy.toml"
    return candidate if candidate.is_file() else None


@lru_cache(maxsize=1)
def _raw_config() -> dict[str, Any]:
    data = _deep_merge(_DEFAULTS, {})
    path = _config_path()
    if path is not None:
        loaded = tomllib.loads(path.read_text(encoding="utf-8"))
        data = _deep_merge(data, loaded)
    return data


# --- typed accessors (callers depend on these, never on the raw dict shape) --- #
def get_db_backend() -> str:
    return str(_raw_config()["db"]["backend"])


def get_db_path() -> Path:
    """Absolute path to the SQLite file, under the (env-overridable) data dir."""
    return get_data_dir() / str(_raw_config()["db"]["path"])


def get_sandbox_provider() -> str:
    return str(_raw_config()["sandbox"]["provider"])


def get_bus_backend() -> str:
    return str(_raw_config()["bus"]["backend"])


def get_artifact_backend() -> str:
    return str(_raw_config()["artifacts"]["backend"])


def get_secrets_backend() -> str:
    return str(_raw_config()["secrets"]["backend"])


def get_default_provider() -> str:
    return str(_raw_config()["gateway"]["default_provider"])


def get_rework_grant_pct() -> int:
    """Revised-brief rework top-up, as a percentage of the child's original allowance — debited
    from the parent assignment's meter (work-model.md §2.2)."""
    return int(_raw_config()["work"]["rework_grant_pct"])


def get_allow_trusted_local() -> bool:
    """The MVP waiver (cli-runtime.md §8): execute-class grants on the subprocess tier are
    refused (TIER_UNSATISFIABLE) unless explicitly waived — loudly, once, logged."""
    return bool(_raw_config()["execution"]["allow_trusted_local"])


def get_runtime_override() -> str:
    """Force every node onto one runtime kind (e.g. 'loop' for keyless CI/dev); empty means
    each role's ``defaultRuntime`` decides (envelope §4)."""
    return str(_raw_config()["execution"]["runtime_override"])


def get_trigger_poll_seconds() -> float:
    """Event-trigger poll interval (standing-orgs.md §3). Defaulted so existing configs need
    no edit; tests shrink it."""
    return float(_raw_config().get("work", {}).get("trigger_poll_seconds", 60))


def get_stall_minutes() -> int:
    """No Step for this long while ``executing`` opens a stall InterventionGate."""
    return int(_raw_config()["work"]["stall_minutes"])


def get_stall_none_steps() -> int:
    """This many consecutive ``delta_kind='none'`` steps opens a stall InterventionGate."""
    return int(_raw_config()["work"]["stall_none_steps"])


def get_repo_source() -> Path | None:
    """The work target the repo executors materialize for each team (mvp.md E8): a path to a
    local git clone. Empty (the default) means the ``examples/target-app`` fixture — the CI
    spine. Set it to point the team at a real repository (e.g. a dedicated clone of Canopy
    itself); the source is only ever read (cloned from), never written."""
    raw = str(_raw_config()["repo"]["source"]).strip()
    return Path(raw).expanduser() if raw else None


def get_provider_concurrency() -> dict[str, int]:
    return {k: int(v) for k, v in _raw_config()["gateway"]["concurrency"].items()}


def get_prices() -> dict[str, dict[str, dict[str, float]]]:
    """``{provider: {model: {"input": usd_per_mtok, "output": usd_per_mtok}}}`` (estimates)."""
    return _raw_config().get("prices", {})  # type: ignore[return-value]


def get_capacity_enabled() -> bool:
    """[capacity] enabled — the C2 substrate gate (defaults off). The CANOPY_CAPACITY
    env var overrides for tests and scratch servers, mirroring CANOPY_DATA_DIR."""
    env = os.environ.get("CANOPY_CAPACITY")
    if env is not None:
        return env.lower() in ("1", "true", "on", "yes")
    return bool(_raw_config().get("capacity", {}).get("enabled", False))


def get_capacity_reading_ttl_s() -> int:
    """[capacity] reading_ttl_s — how long a tier-1 reading counts as fresh (02 §4)."""
    return int(_raw_config().get("capacity", {}).get("reading_ttl_s", 900))


def get_capacity_attribution_window_s() -> int:
    """[capacity] attribution_window_s — the EWMA horizon for burn rates (02 §5)."""
    return int(_raw_config().get("capacity", {}).get("attribution_window_s", 3600))


def get_capacity_reading_retention_days() -> int:
    """[capacity] reading_retention_days — how long append-only readings are kept
    before hourly compaction (02 §9.3, decided at C7: 30). Each window's newest reading
    always survives (it is the state's provenance); ``0`` keeps everything forever."""
    return int(_raw_config().get("capacity", {}).get("reading_retention_days", 30))


def get_capacity_event_retention_days() -> int:
    """[capacity] event_retention_days — the feed/audit rows' retention (default 90;
    the console shows the last 100 either way). ``0`` keeps everything forever."""
    return int(_raw_config().get("capacity", {}).get("event_retention_days", 90))


def get_capacity_anthropic_source() -> str:
    """[capacity.anthropic] source — 'observed' (default) or 'usage-endpoint' (S4,
    [Community], ToS-gray; the compliance posture lives in adapters/anthropic_usage.py
    and is the operator's explicit call, never a default — 03 §2)."""
    return str(
        _raw_config().get("capacity", {}).get("anthropic", {}).get("source", "observed")
    )


def get_capacity_anthropic_poll_s() -> int:
    """[capacity.anthropic] poll_interval_s — usage-endpoint mode only. Floor 180 s:
    community-verified etiquette for an aggressively rate-limited surface (03 §2)."""
    raw = int(
        _raw_config().get("capacity", {}).get("anthropic", {}).get("poll_interval_s", 300)
    )
    return max(180, raw)


def get_scheduler_enabled() -> bool:
    """[scheduler] enabled — the C4 governor gate (inert at C1, defaults off)."""
    return bool(_raw_config().get("scheduler", {}).get("enabled", False))


def get_scheduler_resume_jitter_s() -> int:
    """[scheduler] resume_jitter_s — capacity-gate auto-resume jitter (04 §7)."""
    return int(_raw_config().get("scheduler", {}).get("resume_jitter_s", 120))
