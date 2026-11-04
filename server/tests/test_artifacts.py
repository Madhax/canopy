"""Artifact Store — content-addressed, versioned, immutable refs (control-plane.md §7)."""

from __future__ import annotations

import pytest

from canopy_server.artifacts import ArtifactTooLarge, LocalArtifactStore
from canopy_server.db import Db


def _store(tmp_path, **kw) -> LocalArtifactStore:
    return LocalArtifactStore(Db(tmp_path / "canopy.db"), tmp_path / "artifacts", **kw)


def test_put_resolve_read_roundtrip(tmp_path):
    store = _store(tmp_path)
    meta = store.put("o1", "acme", "a_be", "q3-report", "document", b"hello world")
    assert meta.ref == "team://acme/a_be/q3-report@1"
    assert meta.version == 1 and meta.prevVersionRef is None
    assert store.resolve(meta.ref).sha256 == meta.sha256
    assert store.read(meta.ref) == b"hello world"


def test_new_version_links_back(tmp_path):
    store = _store(tmp_path)
    v1 = store.put("o1", "acme", "a_be", "pr", "code-patch", b"v1 content")
    v2 = store.put("o1", "acme", "a_be", "pr", "code-patch", b"v2 content")
    assert v2.version == 2
    assert v2.ref == "team://acme/a_be/pr@2"
    assert v2.prevVersionRef == v1.ref
    assert store.read(v1.ref) == b"v1 content"  # old version immutable, still readable


def test_identical_content_dedupes(tmp_path):
    store = _store(tmp_path)
    a = store.put("o1", "acme", "a_be", "pr", "code-patch", b"same")
    b = store.put("o1", "acme", "a_be", "pr", "code-patch", b"same")
    assert a.ref == b.ref and a.version == 1  # no phantom @2


def test_lineage(tmp_path):
    store = _store(tmp_path)
    store.put("o1", "acme", "a_be", "pr", "code-patch", b"1")
    store.put("o1", "acme", "a_be", "pr", "code-patch", b"2")
    v3 = store.put("o1", "acme", "a_be", "pr", "code-patch", b"3")
    versions = [m.version for m in store.lineage(v3.ref)]
    assert versions == [1, 2, 3]


def test_size_cap(tmp_path):
    store = _store(tmp_path, max_bytes=8)
    with pytest.raises(ArtifactTooLarge):
        store.put("o1", "acme", "a_be", "big", "dataset", b"123456789")


def test_list_scoping(tmp_path):
    store = _store(tmp_path)
    store.put("o1", "acme", "a_be", "x", "document", b"1")
    store.put("o1", "acme", "a_qa", "y", "document", b"2")
    assert len(store.list("o1")) == 2
    assert [m.name for m in store.list("o1", "a_qa")] == ["y"]


def test_legacy_org_scheme_reads_forever(tmp_path):
    """Readers accept org:// indefinitely (design/organizations/07 §2.4)."""
    store = _store(tmp_path)
    meta = store.put("t1", "acme", "a_be", "legacy-doc", "document", b"content")
    assert meta.ref.startswith("team://")
    legacy = meta.ref.replace("team://", "org://", 1)
    assert store.resolve(legacy) is not None
    assert store.resolve(legacy).ref == meta.ref
    assert store.read(legacy) == b"content"


def test_pre_c1_artifact_table_is_migrated(tmp_path):
    """A DB from before the C1 rename has ``org_id``/``org_slug`` on artifacts_artifact. The
    boot migration must rename BOTH — a missed ``org_slug`` made every artifact write fail
    with "no such column: team_slug" (agents looped on HTTP 500, nothing ever delivered)."""
    import sqlite3

    path = tmp_path / "canopy.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE artifacts_artifact (id TEXT PRIMARY KEY, ref TEXT NOT NULL UNIQUE, "
        "org_id TEXT NOT NULL, org_slug TEXT NOT NULL, node_id TEXT NOT NULL, task_id TEXT, "
        "name TEXT NOT NULL, type TEXT NOT NULL, filename TEXT, size INTEGER NOT NULL, "
        "sha256 TEXT NOT NULL, version INTEGER NOT NULL, prev_version_ref TEXT, "
        "created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO artifacts_artifact VALUES ('art_old', 'org://acme/a_be/report@1', 'o1', "
        "'acme', 'a_be', NULL, 'report', 'document', NULL, 3, 'abc', 1, NULL, '2026-07-01')"
    )
    conn.commit()
    conn.close()

    store = LocalArtifactStore(Db(path), tmp_path / "artifacts")
    meta = store.put("o1", "acme", "a_be", "report", "document", b"new content")
    assert meta.ref == "team://acme/a_be/report@2"  # versions on from the legacy row
    assert meta.prevVersionRef == "team://acme/a_be/report@1"  # ref rewritten org:// → team://
