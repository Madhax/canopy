"""Artifact Store — immutable, versioned, addressable work outputs (control-plane.md §7).

The only way work leaves a sandbox (invariant 2: exchange is artifacts and messages, platform-
mediated, or nothing). Content-addressed blobs on disk, metadata in SQLite; refs follow the domain
grammar ``org://<org-slug>/<node-or-team>/<name>@<version>`` — immutable, new versions link back,
refs never dangle. The interface is object-store-shaped (``put``/``get``/``resolve``/``list``/
``lineage``) so the local-disk backend swaps for S3/GCS/MinIO with no change to provenance or refs.

Designed as Phase-2 A4; built now as Phase-3 E1 exactly per the design — nothing changes.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from .db import Db, register_schema
from .deps import now_iso
from .ids import new_artifact_id
from .registry import Registry

DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB per artifact (control-plane.md §7)

SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts_artifact (
    id                 TEXT PRIMARY KEY,
    ref                TEXT NOT NULL UNIQUE,
    org_id             TEXT NOT NULL,
    org_slug           TEXT NOT NULL,
    node_id            TEXT NOT NULL,
    task_id            TEXT,
    name               TEXT NOT NULL,
    type               TEXT NOT NULL,
    filename           TEXT,
    size               INTEGER NOT NULL,
    sha256             TEXT NOT NULL,
    version            INTEGER NOT NULL,
    prev_version_ref   TEXT,
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_artifact_name ON artifacts_artifact (org_id, node_id, name, version);
"""
register_schema(SCHEMA)


class ArtifactMeta(BaseModel):
    id: str
    ref: str
    orgId: str
    nodeId: str
    taskId: str | None
    name: str
    type: str
    filename: str | None
    size: int
    sha256: str
    version: int
    prevVersionRef: str | None
    createdAt: str


class ArtifactTooLarge(Exception):
    pass


class ArtifactStore(ABC):
    @abstractmethod
    def put(self, org_id: str, org_slug: str, node_id: str, name: str, type: str,
            content: bytes, *, task_id: str | None = None,
            filename: str | None = None) -> ArtifactMeta: ...

    @abstractmethod
    def resolve(self, ref: str) -> ArtifactMeta | None: ...

    @abstractmethod
    def read(self, ref: str) -> bytes | None: ...

    @abstractmethod
    def list(self, org_id: str, node_id: str | None = None) -> list[ArtifactMeta]: ...

    @abstractmethod
    def lineage(self, ref: str) -> list[ArtifactMeta]:
        """All versions of a ref's name (oldest → newest)."""


artifact_store_registry: Registry[ArtifactStore] = Registry("artifact store")


def _row_to_meta(row) -> ArtifactMeta:
    return ArtifactMeta(
        id=row["id"], ref=row["ref"], orgId=row["org_id"], nodeId=row["node_id"],
        taskId=row["task_id"], name=row["name"], type=row["type"], filename=row["filename"],
        size=row["size"], sha256=row["sha256"], version=row["version"],
        prevVersionRef=row["prev_version_ref"], createdAt=row["created_at"],
    )


@artifact_store_registry.register("local")
class LocalArtifactStore(ArtifactStore):
    def __init__(self, db: Db, blobs_root: Path, *, max_bytes: int = DEFAULT_MAX_BYTES):
        self.db = db
        self.blobs_root = blobs_root
        self.max_bytes = max_bytes

    def _blob_path(self, sha256: str) -> Path:
        return self.blobs_root / sha256[:2] / sha256

    def put(self, org_id, org_slug, node_id, name, type, content, *, task_id=None,
            filename=None) -> ArtifactMeta:
        if len(content) > self.max_bytes:
            raise ArtifactTooLarge(f"{len(content)} bytes exceeds cap {self.max_bytes}")
        sha256 = hashlib.sha256(content).hexdigest()
        ts = now_iso()
        with self.db.transaction() as conn:
            latest = conn.execute(
                "SELECT * FROM artifacts_artifact WHERE org_id=? AND node_id=? AND name=? "
                "ORDER BY version DESC LIMIT 1",
                (org_id, node_id, name),
            ).fetchone()
            # Dedupe: identical content under the same name is the same artifact (idempotent).
            if latest is not None and latest["sha256"] == sha256:
                return _row_to_meta(latest)
            version = (latest["version"] + 1) if latest else 1
            prev_ref = latest["ref"] if latest else None
            ref = f"org://{org_slug}/{node_id}/{name}@{version}"
            aid = new_artifact_id()
            conn.execute(
                "INSERT INTO artifacts_artifact (id, ref, org_id, org_slug, node_id, task_id, "
                "name, type, filename, size, sha256, version, prev_version_ref, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (aid, ref, org_id, org_slug, node_id, task_id, name, type, filename,
                 len(content), sha256, version, prev_ref, ts),
            )
        # Write the blob content-addressed (idempotent: same hash → same path).
        path = self._blob_path(sha256)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return ArtifactMeta(
            id=aid, ref=ref, orgId=org_id, nodeId=node_id, taskId=task_id, name=name, type=type,
            filename=filename, size=len(content), sha256=sha256, version=version,
            prevVersionRef=prev_ref, createdAt=ts,
        )

    def resolve(self, ref: str) -> ArtifactMeta | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts_artifact WHERE ref=?", (ref,)
            ).fetchone()
        return _row_to_meta(row) if row else None

    def read(self, ref: str) -> bytes | None:
        meta = self.resolve(ref)
        if meta is None:
            return None
        path = self._blob_path(meta.sha256)
        return path.read_bytes() if path.is_file() else None

    def list(self, org_id: str, node_id: str | None = None) -> list[ArtifactMeta]:
        with self.db.connect() as conn:
            if node_id is None:
                rows = conn.execute(
                    "SELECT * FROM artifacts_artifact WHERE org_id=? ORDER BY created_at",
                    (org_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM artifacts_artifact WHERE org_id=? AND node_id=? "
                    "ORDER BY created_at",
                    (org_id, node_id),
                ).fetchall()
        return [_row_to_meta(r) for r in rows]

    def lineage(self, ref: str) -> list[ArtifactMeta]:
        meta = self.resolve(ref)
        if meta is None:
            return []
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts_artifact WHERE org_id=? AND node_id=? AND name=? "
                "ORDER BY version",
                (meta.orgId, meta.nodeId, meta.name),
            ).fetchall()
        return [_row_to_meta(r) for r in rows]
