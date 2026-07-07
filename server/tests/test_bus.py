"""SqliteBus — the distribution queue (data-plane.md §3, Paperclip wakeup-queue patterns).

FIFO + atomic claim/visibility, plus the two robustness features borrowed from Paperclip's
``agent_wakeup_requests``: idempotency-key dedupe and coalescing.
"""

from __future__ import annotations

from canopy_server.bus import Envelope, SqliteBus
from canopy_server.db import Db


def _bus(tmp_path) -> SqliteBus:
    return SqliteBus(Db(tmp_path / "canopy.db"))


def _env(i: int, to: str = "n1") -> Envelope:
    return Envelope(
        id=f"msg{i}", actuationId="act", fromNodeId="a", toNodeId=to,
        a2aPayload={"i": i}, ts="2026-07-06T00:00:00Z",
    )


def test_fifo_order(tmp_path):
    bus = _bus(tmp_path)
    bus.publish("t", _env(1))
    bus.publish("t", _env(2))
    bus.publish("t", _env(3))
    d = bus.poll("t", "c", 10, 30)
    assert [x.envelope.id for x in d] == ["msg1", "msg2", "msg3"]


def test_claim_hides_until_visibility_expires(tmp_path):
    bus = _bus(tmp_path)
    bus.publish("t", _env(1))
    first = bus.poll("t", "c", 10, 30)
    assert len(first) == 1
    # Locked → a second poll sees nothing.
    assert bus.poll("t", "c", 10, 30) == []
    # Force the lock to expire, then it redelivers with a bumped attempt count.
    with Db(tmp_path / "canopy.db").transaction() as conn:
        conn.execute("UPDATE router_queue SET locked_until='2000-01-01T00:00:00Z'")
    again = bus.poll("t", "c", 10, 30)
    assert len(again) == 1 and again[0].attempts == 2


def test_idempotency_key_dedupes(tmp_path):
    bus = _bus(tmp_path)
    a = bus.publish("t", _env(1), idempotency_key="k")
    b = bus.publish("t", _env(2), idempotency_key="k")
    assert a == b
    assert bus.depth("t") == 1


def test_coalescing_collapses_nudges(tmp_path):
    bus = _bus(tmp_path)
    bus.publish("t", _env(1), coalesce_key="wake")
    bus.publish("t", _env(2), coalesce_key="wake")
    bus.publish("t", _env(3), coalesce_key="wake")
    assert bus.depth("t") == 1
    d = bus.poll("t", "c", 10, 30)
    assert len(d) == 1 and d[0].coalescedCount == 2


def test_ack_clears_depth(tmp_path):
    bus = _bus(tmp_path)
    bus.publish("t", _env(1))
    d = bus.poll("t", "c", 10, 30)
    bus.ack(d[0].id)
    assert bus.depth("t") == 0


def test_nack_requeues_then_dead_letters(tmp_path):
    bus = _bus(tmp_path)
    bus.publish("t", _env(1), max_attempts=2)

    d = bus.poll("t", "c", 10, 30)  # attempts=1
    dead, _env_none = bus.nack(d[0].id, requeue=True)
    assert dead is False  # 1 < 2 → requeued

    d = bus.poll("t", "c", 10, 30)  # attempts=2
    dead, env = bus.nack(d[0].id, requeue=True)
    assert dead is True and env.id == "msg1"  # 2 >= max → dead-lettered
    assert bus.depth("t") == 0  # dead is not a live depth
