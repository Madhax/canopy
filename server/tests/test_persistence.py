"""SQLite org store — the phase-1 contract on a new backend, plus non-destructive migration."""

from __future__ import annotations

import json

from canopy_server.db import Db
from canopy_server.models import Agent, Organization, RoleRef, Salary
from canopy_server.sqlite_store import SqliteOrgStore
from canopy_server.store import NotFound


def _org(oid="mig-1"):
    return Organization(
        id=oid,
        name="Mig",
        organizationType="product-engineering",
        updatedAt="2026-07-05T00:00:00Z",
        agents=[
            Agent(
                id="a_root",
                name="Lead",
                role=RoleRef(key="engineering-lead", version=1),
                managerId=None,
                salary=Salary(perAssignmentAllowance=1000),
            )
        ],
    )


def test_write_read_roundtrip(tmp_path):
    store = SqliteOrgStore(Db(tmp_path / "canopy.db"))
    store.write(_org("o1"))
    assert store.exists("o1")
    assert store.read("o1").agents[0].name == "Lead"
    assert store.list_ids() == ["o1"]


def test_read_missing_raises(tmp_path):
    store = SqliteOrgStore(Db(tmp_path / "canopy.db"))
    try:
        store.read("nope")
    except NotFound:
        pass
    else:
        raise AssertionError("expected NotFound")


def test_delete(tmp_path):
    store = SqliteOrgStore(Db(tmp_path / "canopy.db"))
    store.write(_org("o1"))
    assert store.delete("o1") is True
    assert store.delete("o1") is False


def test_json_docs_migrate_non_destructively(tmp_path):
    json_dir = tmp_path / "organizations"
    json_dir.mkdir()
    doc = _org("legacy-1").model_dump(by_alias=True, mode="json")
    legacy_file = json_dir / "legacy-1.json"
    legacy_file.write_text(json.dumps(doc), encoding="utf-8")

    store = SqliteOrgStore(Db(tmp_path / "canopy.db"), migrate_from=json_dir)
    assert store.exists("legacy-1")
    assert store.read("legacy-1").name == "Mig"
    # non-destructive: the original file is untouched
    assert legacy_file.is_file()


def test_migration_does_not_clobber_existing_rows(tmp_path):
    db = Db(tmp_path / "canopy.db")
    store = SqliteOrgStore(db)
    edited = _org("dup-1")
    edited.name = "Edited In DB"
    store.write(edited)

    json_dir = tmp_path / "organizations"
    json_dir.mkdir()
    stale = _org("dup-1").model_dump(by_alias=True, mode="json")
    (json_dir / "dup-1.json").write_text(json.dumps(stale), encoding="utf-8")

    # Re-construct with migration: the id already exists, so the DB copy wins.
    store2 = SqliteOrgStore(db, migrate_from=json_dir)
    assert store2.read("dup-1").name == "Edited In DB"
