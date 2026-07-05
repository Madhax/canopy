"""JSON file store — one file per top-level organization document.

The only throwaway part of the stack (docs §5): the REST contract is the seam the real control
plane inherits, but persistence here is just files. Writes are atomic (temp file + ``os.replace``)
so a crash mid-write never corrupts a document.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import Organization


class StoreError(Exception):
    pass


class NotFound(StoreError):
    pass


class JsonFileStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "organizations"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, doc_id: str) -> Path:
        # doc ids are server-assigned UUIDs; guard against path traversal regardless.
        safe = doc_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.root / f"{safe}.json"

    def exists(self, doc_id: str) -> bool:
        return self._path(doc_id).is_file()

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))

    def read_raw(self, doc_id: str) -> dict:
        path = self._path(doc_id)
        if not path.is_file():
            raise NotFound(doc_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def read(self, doc_id: str) -> Organization:
        return Organization.model_validate(self.read_raw(doc_id))

    def read_all(self) -> list[Organization]:
        out: list[Organization] = []
        for doc_id in self.list_ids():
            try:
                out.append(self.read(doc_id))
            except Exception:
                # A malformed file on disk should not take down the whole list.
                continue
        return out

    def write(self, org: Organization) -> None:
        path = self._path(org.id)
        payload = org.model_dump(by_alias=True, mode="json")
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        # atomic: write to a temp file in the same dir, fsync, then replace.
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def delete(self, doc_id: str) -> bool:
        path = self._path(doc_id)
        if path.is_file():
            path.unlink()
            return True
        return False
