"""Agent Directory — registration, heartbeat, staleness."""

from __future__ import annotations

from canopy_server.db import Db
from canopy_server.directory import AgentDirectory


def _dir(tmp_path) -> AgentDirectory:
    return AgentDirectory(Db(tmp_path / "canopy.db"))


def test_provision_register_heartbeat(tmp_path):
    d = _dir(tmp_path)
    d.upsert_provisioning("act1", "n1")
    assert d.get("act1", "n1").status == "provisioning"

    d.register("act1", "n1", "http://127.0.0.1:5555", {"name": "Lead"})
    agent = d.get("act1", "n1")
    assert agent.status == "idle"
    assert agent.endpointUrl == "http://127.0.0.1:5555"
    assert agent.agentCard == {"name": "Lead"}

    d.heartbeat("act1", "n1", "engaged")
    assert d.get("act1", "n1").status == "engaged"


def test_stale_detection(tmp_path):
    d = _dir(tmp_path)
    d.upsert_provisioning("act1", "n1")
    d.register("act1", "n1", "http://x", {})
    # A future threshold makes every heartbeat look stale.
    assert [a.nodeId for a in d.stale("act1", "2999-01-01T00:00:00Z")] == ["n1"]
    # A past threshold makes none stale.
    assert d.stale("act1", "2000-01-01T00:00:00Z") == []


def test_remove_actuation(tmp_path):
    d = _dir(tmp_path)
    d.upsert_provisioning("act1", "n1")
    d.upsert_provisioning("act1", "n2")
    d.remove_actuation("act1")
    assert d.list("act1") == []
