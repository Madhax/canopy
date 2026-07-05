"""Runtime configuration (env-driven, with sane defaults)."""

from __future__ import annotations

import os
from pathlib import Path

# repo_root/server/src/canopy_server/config.py -> repo_root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def get_port() -> int:
    return int(os.environ.get("CANOPY_PORT", "8700"))


def get_data_dir() -> Path:
    raw = os.environ.get("CANOPY_DATA_DIR")
    path = Path(raw) if raw else _REPO_ROOT / "data"
    return path


def get_ui_dist() -> Path:
    """Built UI to serve in production (``pnpm build`` output)."""
    return _REPO_ROOT / "ui" / "dist"
