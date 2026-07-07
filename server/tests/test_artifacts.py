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
    assert meta.ref == "org://acme/a_be/q3-report@1"
    assert meta.version == 1 and meta.prevVersionRef is None
    assert store.resolve(meta.ref).sha256 == meta.sha256
    assert store.read(meta.ref) == b"hello world"


def test_new_version_links_back(tmp_path):
    store = _store(tmp_path)
    v1 = store.put("o1", "acme", "a_be", "pr", "code-patch", b"v1 content")
    v2 = store.put("o1", "acme", "a_be", "pr", "code-patch", b"v2 content")
    assert v2.version == 2
    assert v2.ref == "org://acme/a_be/pr@2"
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
