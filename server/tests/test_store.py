from pathlib import Path

from canopy_server.models import Agent, Organization, RoleRef, Salary
from canopy_server.store import JsonFileStore, NotFound


def _org(oid="o1"):
    return Organization(
        id=oid,
        name="T",
        organizationType="product-engineering",
        agents=[
            Agent(
                id="a_root",
                name="Lead",
                role=RoleRef(key="engineering-lead", version=1),
                managerId=None,
                salary=Salary(perAssignmentAllowance=160000),
            )
        ],
    )


def test_write_read_roundtrip(tmp_path: Path):
    store = JsonFileStore(tmp_path)
    org = _org()
    store.write(org)
    assert store.exists("o1")
    back = store.read("o1")
    assert back.id == "o1"
    assert back.agents[0].name == "Lead"


def test_read_missing_raises(tmp_path: Path):
    store = JsonFileStore(tmp_path)
    try:
        store.read("nope")
    except NotFound:
        pass
    else:
        raise AssertionError("expected NotFound")


def test_atomic_write_leaves_no_temp_files(tmp_path: Path):
    store = JsonFileStore(tmp_path)
    store.write(_org())
    leftovers = list((tmp_path / "organizations").glob("*.tmp"))
    assert leftovers == []


def test_delete(tmp_path: Path):
    store = JsonFileStore(tmp_path)
    store.write(_org())
    assert store.delete("o1") is True
    assert store.delete("o1") is False
    assert not store.exists("o1")


def test_read_all_skips_corrupt(tmp_path: Path):
    store = JsonFileStore(tmp_path)
    store.write(_org("good"))
    (store.root / "broken.json").write_text("{ not json", encoding="utf-8")
    orgs = store.read_all()
    assert [o.id for o in orgs] == ["good"]
