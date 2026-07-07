"""Message Router — chart-derived channels + topology enforcement (data-plane.md §1–2)."""

from __future__ import annotations

import pytest

from canopy_server.bus import SqliteBus
from canopy_server.db import Db
from canopy_server.models import Agent, Organization, RoleRef, Salary
from canopy_server.router import ChannelForbidden, MessageRouter, inbox_topic


def _setup(tmp_path):
    db = Db(tmp_path / "canopy.db")
    bus = SqliteBus(db)
    return db, bus, MessageRouter(db, bus)


def _org() -> Organization:
    def agent(aid, mgr):
        return Agent(id=aid, name=aid, role=RoleRef(key="backend-engineer"), managerId=mgr,
                     salary=Salary(perAssignmentAllowance=1000))
    return Organization(
        id="o", name="O", organizationType="product-engineering",
        agents=[agent("a_root", None), agent("a_be", "a_root"), agent("a_qa", "a_root")],
    )


def test_channel_topology(tmp_path):
    _db, _bus, router = _setup(tmp_path)
    router.derive_channels("act", _org())
    assert router.channel_allowed("act", "a_root", "a_be")  # manager → report
    assert router.channel_allowed("act", "a_be", "a_root")  # report → manager
    assert not router.channel_allowed("act", "a_be", "a_qa")  # siblings — forbidden
    assert router.channel_allowed("act", "operator", "a_qa")  # operator → any
    assert set(router.reports_of("act", "a_root")) == {"a_be", "a_qa"}  # reports only, not upward


def test_send_enqueues_and_forbidden_raises(tmp_path):
    _db, bus, router = _setup(tmp_path)
    router.derive_channels("act", _org())

    sent = router.send("act", "a_root", "a_be", {"brief": "do the thing"})
    assert bus.depth(inbox_topic("act", "a_be")) == 1
    assert sent.topic == inbox_topic("act", "a_be")

    with pytest.raises(ChannelForbidden):
        router.send("act", "a_be", "a_qa", {"x": 1})  # sibling call


def test_broadcast_hits_reports_only(tmp_path):
    _db, bus, router = _setup(tmp_path)
    router.derive_channels("act", _org())
    msgs = router.broadcast("act", "a_root", {"note": "standup"})
    assert len(msgs) == 2  # a_be + a_qa, never upward
    assert bus.depth(inbox_topic("act", "a_be")) == 1
    assert bus.depth(inbox_topic("act", "a_qa")) == 1


def test_clear_actuation_drops_channels_and_queue(tmp_path):
    _db, bus, router = _setup(tmp_path)
    router.derive_channels("act", _org())
    router.send("act", "a_root", "a_be", {})
    router.clear_actuation("act")
    assert not router.channel_allowed("act", "a_root", "a_be")
    assert bus.depth(inbox_topic("act", "a_be")) == 0
