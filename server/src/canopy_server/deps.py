"""Shared FastAPI dependencies + small helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

from .config import get_data_dir
from .store import JsonFileStore


@lru_cache(maxsize=8)
def _store_for(path_str: str) -> JsonFileStore:
    from pathlib import Path

    return JsonFileStore(Path(path_str))


def get_store() -> JsonFileStore:
    return _store_for(str(get_data_dir()))


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
