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


def get_provider_concurrency() -> dict[str, int]:
    return {k: int(v) for k, v in _raw_config()["gateway"]["concurrency"].items()}


def get_prices() -> dict[str, dict[str, dict[str, float]]]:
    """``{provider: {model: {"input": usd_per_mtok, "output": usd_per_mtok}}}`` (estimates)."""
    return _raw_config().get("prices", {})  # type: ignore[return-value]
