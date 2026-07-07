"""Budget Ledger correctness — the money path (risks IM-5, AR-3).

Covers the settle math, the mechanical hard-stop under real thread contention (the race that would
let two agents both "win" the last of a budget), and step-id idempotency (a redelivered step must
settle exactly once).
"""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from canopy_server.db import Db
from canopy_server.ledger import BudgetExhausted, SqliteLedger


def _ledger(tmp_path: Path) -> SqliteLedger:
    return SqliteLedger(Db(tmp_path / "canopy.db"))


def _record(ledger, meter, step_id, tokens, reserved):
    return ledger.record(
        meter.id, step_id=step_id, org_id="o1", node_id=meter.nodeId,
        actuation_id=meter.actuationId, provider="mock", model="mock-1",
        input_tokens=0, output_tokens=tokens, est_cost_micros=0, reserved=reserved,
    )


def test_reserve_record_settles(tmp_path):
    ledger = _ledger(tmp_path)
    m = ledger.open_meter("act", "n1", 1000)
    res = ledger.reserve(m.id, 100)
    assert res.amount == 100
    assert ledger.get_meter(m.id).reserved == 100
    out = _record(ledger, m, "st1", tokens=40, reserved=100)
    assert out.meter.spent == 40
    assert out.meter.reserved == 0  # reservation released, actual booked


def test_hard_stop_refuses_before_dispatch(tmp_path):
    ledger = _ledger(tmp_path)
    m = ledger.open_meter("act", "n1", 100, hard_stop=True)
    ledger.reserve(m.id, 60)
    with pytest.raises(BudgetExhausted):
        ledger.reserve(m.id, 60)  # 60 + 60 > 100 → refused, no dispatch happens
    assert ledger.get_meter(m.id).state == "exhausted"


def test_soft_meter_never_refuses(tmp_path):
    ledger = _ledger(tmp_path)
    m = ledger.open_meter("act", "n1", 100, hard_stop=False)
    ledger.reserve(m.id, 80)
    ledger.reserve(m.id, 80)  # soft meter allows overshoot
    assert ledger.get_meter(m.id).reserved == 160


def test_idempotent_record_charges_once(tmp_path):
    ledger = _ledger(tmp_path)
    m = ledger.open_meter("act", "n1", 1000)
    ledger.reserve(m.id, 100)
    first = _record(ledger, m, "dup-step", tokens=100, reserved=100)
    assert first.duplicate is False and first.meter.spent == 100
    # A redelivered step with the same id must not double-charge (risk AR-3).
    second = _record(ledger, m, "dup-step", tokens=100, reserved=100)
    assert second.duplicate is True
    assert ledger.get_meter(m.id).spent == 100


def test_warn_crosses_once(tmp_path):
    ledger = _ledger(tmp_path)
    m = ledger.open_meter("act", "n1", 100, warn_threshold_pct=80)
    ledger.reserve(m.id, 85)
    out1 = _record(ledger, m, "s1", tokens=85, reserved=85)
    assert out1.crossedWarn is True
    ledger.reserve(m.id, 5)
    out2 = _record(ledger, m, "s2", tokens=5, reserved=5)
    assert out2.crossedWarn is False  # already warned; only the crossing edge reports


def test_raise_meter_reopens(tmp_path):
    ledger = _ledger(tmp_path)
    m = ledger.open_meter("act", "n1", 100)
    ledger.reserve(m.id, 100)
    with pytest.raises(BudgetExhausted):
        ledger.reserve(m.id, 1)
    ledger.raise_meter(m.id, 100)
    assert ledger.get_meter(m.id).state == "open"
    ledger.reserve(m.id, 50)  # room again after top-up


def test_concurrent_reserves_never_over_authorize(tmp_path):
    """50 threads each try reserve(100)+record against a 1000-token hard-stop meter.

    Exactly 10 may succeed; spend must land at 1000, never above — the mechanical hard-stop must
    hold under real write contention (risk IM-5).
    """
    ledger = _ledger(tmp_path)
    m = ledger.open_meter("act", "n1", 1000, hard_stop=True)

    def worker(i: int) -> bool:
        try:
            res = ledger.reserve(m.id, 100)
        except BudgetExhausted:
            return False
        _record(ledger, m, f"st{i}", tokens=100, reserved=res.amount)
        return True

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(worker, range(50)))

    final = ledger.get_meter(m.id)
    assert sum(results) == 10
    assert final.spent == 1000
    assert final.reserved == 0


def test_randomized_sequences_keep_invariants(tmp_path):
    """Fuzz interleavings: spent and reserved never go negative and hard-stop never over-commits."""
    ledger = _ledger(tmp_path)
    rng = random.Random(1234)
    for trial in range(30):
        m = ledger.open_meter("act", f"n{trial}", 500, hard_stop=True)
        step = 0
        for _ in range(40):
            action = rng.choice(["reserve_record", "reserve_only"])
            amount = rng.randint(1, 120)
            try:
                res = ledger.reserve(m.id, amount)
            except BudgetExhausted:
                continue
            if action == "reserve_record":
                step += 1
                _record(ledger, m, f"n{trial}-s{step}", tokens=amount, reserved=res.amount)
            else:
                ledger.release(res)
            cur = ledger.get_meter(m.id)
            assert cur.spent >= 0 and cur.reserved >= 0
            assert cur.spent + cur.reserved <= cur.allowance  # hard-stop invariant
