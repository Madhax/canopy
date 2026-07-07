"""Budget Ledger — salaries become meters, steps become spend, hard-stops are mechanical.

This is the money path, "the one bug class Canopy can't shrug off" (risk IM-5), so the whole
module is built for correctness over cleverness:

* **Every mutation is one ``BEGIN IMMEDIATE`` transaction** (see ``db.transaction``). Reserve
  reads the meter, checks the budget, and writes the reservation as a single atomic unit — so the
  hard-stop check and the spend it authorizes can never interleave with another agent's step.
  This is what makes invariant 7 mechanical rather than "a request politely made to an LLM".
* **Reserve before dispatch; record after.** The gateway reserves an upper-bound estimate
  (input estimate + maxOutputTokens) *before* calling the provider, and records provider-
  authoritative actuals *after*. Because ``reserve`` only ever grants ``amount`` when
  ``spent + reserved + amount <= allowance`` (for hard-stop meters), a dispatch that would breach
  the budget is refused *before the call is made*, not detected after the money is gone.
* **Step-id idempotency.** ``record`` dedupes on ``step_id`` (also a UNIQUE column), so a step
  redelivered by the at-least-once bus (risk AR-3) settles exactly once — spent tokens stay spent,
  never double-charged.

The interface uses the Phase-3 names now (``open_meter`` / ``reserve`` / ``record`` /
``close_meter``) so the Phase-3 swap from "meter per routed task" to real Assignment-bound meters
is an internal change, not an API break (risk AR-5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from .db import Db, register_schema
from .deps import now_iso
from .ids import new_meter_id, new_spend_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_meter (
    id                 TEXT PRIMARY KEY,
    actuation_id       TEXT NOT NULL,
    node_id            TEXT NOT NULL,
    task_id            TEXT,
    allowance          INTEGER NOT NULL,
    reserved           INTEGER NOT NULL DEFAULT 0,
    spent              INTEGER NOT NULL DEFAULT 0,
    state              TEXT NOT NULL DEFAULT 'open',
    warn_threshold_pct REAL NOT NULL DEFAULT 80,
    hard_stop          INTEGER NOT NULL DEFAULT 1,
    warned             INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    closed_at          TEXT
);
CREATE INDEX IF NOT EXISTS ix_meter_node ON ledger_meter (actuation_id, node_id);

CREATE TABLE IF NOT EXISTS ledger_spend_event (
    id              TEXT PRIMARY KEY,
    step_id         TEXT NOT NULL UNIQUE,
    org_id          TEXT NOT NULL,
    actuation_id    TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    task_id         TEXT,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    est_cost_micros INTEGER NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_spend_org ON ledger_spend_event (org_id);
"""
register_schema(SCHEMA)

MeterState = str  # "open" | "exhausted" | "closed"


class BudgetExhausted(Exception):
    """Raised by ``reserve`` when a hard-stop meter cannot cover the requested amount."""

    def __init__(self, meter_id: str):
        self.meter_id = meter_id
        super().__init__(f"budget exhausted for meter {meter_id}")


class Meter(BaseModel):
    id: str
    actuationId: str
    nodeId: str
    taskId: str | None
    allowance: int
    reserved: int
    spent: int
    state: MeterState
    warnThresholdPct: float
    hardStop: bool
    warned: bool
    createdAt: str
    closedAt: str | None = None

    @property
    def available(self) -> int:
        return self.allowance - self.spent - self.reserved


class SpendEvent(BaseModel):
    id: str
    stepId: str
    orgId: str
    actuationId: str
    nodeId: str
    taskId: str | None
    provider: str
    model: str
    inputTokens: int
    outputTokens: int
    estCostMicros: int
    createdAt: str


class Reservation(BaseModel):
    meterId: str
    amount: int


class RecordOutcome(BaseModel):
    meter: Meter
    spendEvent: SpendEvent
    crossedWarn: bool = False  # first time this record pushed the meter past its warn threshold
    exhausted: bool = False
    duplicate: bool = False


class BudgetLedger(ABC):
    @abstractmethod
    def open_meter(
        self, actuation_id: str, node_id: str, allowance: int, *,
        warn_threshold_pct: float = 80, hard_stop: bool = True, task_id: str | None = None,
    ) -> Meter: ...

    @abstractmethod
    def reserve(self, meter_id: str, amount: int) -> Reservation: ...

    @abstractmethod
    def record(
        self, meter_id: str, *, step_id: str, org_id: str, node_id: str, actuation_id: str,
        provider: str, model: str, input_tokens: int, output_tokens: int, est_cost_micros: int,
        reserved: int, task_id: str | None = None,
    ) -> RecordOutcome: ...

    @abstractmethod
    def release(self, reservation: Reservation) -> None:
        """Return an unused reservation to the meter (e.g. the provider call failed)."""

    @abstractmethod
    def close_meter(self, meter_id: str) -> None: ...

    @abstractmethod
    def raise_meter(self, meter_id: str, additional: int) -> Meter | None: ...

    @abstractmethod
    def get_meter(self, meter_id: str) -> Meter | None: ...

    @abstractmethod
    def rollup(self, org_id: str, group_by: str) -> list[dict]: ...


def _row_to_meter(row) -> Meter:
    return Meter(
        id=row["id"],
        actuationId=row["actuation_id"],
        nodeId=row["node_id"],
        taskId=row["task_id"],
        allowance=row["allowance"],
        reserved=row["reserved"],
        spent=row["spent"],
        state=row["state"],
        warnThresholdPct=row["warn_threshold_pct"],
        hardStop=bool(row["hard_stop"]),
        warned=bool(row["warned"]),
        createdAt=row["created_at"],
        closedAt=row["closed_at"],
    )


class SqliteLedger(BudgetLedger):
    def __init__(self, db: Db):
        self.db = db

    def open_meter(
        self, actuation_id, node_id, allowance, *,
        warn_threshold_pct=80, hard_stop=True, task_id=None,
    ) -> Meter:
        mid = new_meter_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO ledger_meter (id, actuation_id, node_id, task_id, allowance, "
                "warn_threshold_pct, hard_stop, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (mid, actuation_id, node_id, task_id, allowance, warn_threshold_pct,
                 1 if hard_stop else 0, ts),
            )
        return Meter(
            id=mid, actuationId=actuation_id, nodeId=node_id, taskId=task_id, allowance=allowance,
            reserved=0, spent=0, state="open", warnThresholdPct=warn_threshold_pct,
            hardStop=hard_stop, warned=False, createdAt=ts,
        )

    def reserve(self, meter_id: str, amount: int) -> Reservation:
        amount = max(0, amount)
        # Decide and persist inside the transaction, but raise *after* it commits — raising inside
        # would roll back the very "mark exhausted" write we want to keep.
        refuse = False
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM ledger_meter WHERE id = ?", (meter_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"no meter {meter_id!r}")
            m = _row_to_meter(row)
            available = m.allowance - m.spent - m.reserved
            if m.state == "closed":
                refuse = True
            elif m.hardStop and (m.state == "exhausted" or amount > available):
                conn.execute("UPDATE ledger_meter SET state='exhausted' WHERE id=?", (meter_id,))
                refuse = True
            else:
                conn.execute(
                    "UPDATE ledger_meter SET reserved = reserved + ? WHERE id = ?",
                    (amount, meter_id),
                )
        if refuse:
            raise BudgetExhausted(meter_id)
        return Reservation(meterId=meter_id, amount=amount)

    def release(self, reservation: Reservation) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE ledger_meter SET reserved = MAX(0, reserved - ?) WHERE id = ?",
                (reservation.amount, reservation.meterId),
            )

    def record(
        self, meter_id, *, step_id, org_id, node_id, actuation_id, provider, model,
        input_tokens, output_tokens, est_cost_micros, reserved, task_id=None,
    ) -> RecordOutcome:
        tokens = int(input_tokens) + int(output_tokens)
        ts = now_iso()
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM ledger_spend_event WHERE step_id = ?", (step_id,)
            ).fetchone()
            if existing is not None:
                # Idempotent settle: release this call's reservation, don't double-charge.
                conn.execute(
                    "UPDATE ledger_meter SET reserved = MAX(0, reserved - ?) WHERE id = ?",
                    (reserved, meter_id),
                )
                mrow = conn.execute(
                    "SELECT * FROM ledger_meter WHERE id = ?", (meter_id,)
                ).fetchone()
                return RecordOutcome(
                    meter=_row_to_meter(mrow),
                    spendEvent=_spend_row_to_event(existing),
                    duplicate=True,
                    exhausted=_row_to_meter(mrow).state == "exhausted",
                )

            mrow = conn.execute(
                "SELECT * FROM ledger_meter WHERE id = ?", (meter_id,)
            ).fetchone()
            if mrow is None:
                raise KeyError(f"no meter {meter_id!r}")
            before = _row_to_meter(mrow)

            new_spent = before.spent + tokens
            new_reserved = max(0, before.reserved - reserved)
            warn_line = before.allowance * before.warnThresholdPct / 100.0
            crossed_warn = (not before.warned) and new_spent >= warn_line
            exhausted = new_spent >= before.allowance
            new_state = "exhausted" if (before.hardStop and exhausted) else before.state
            if before.state == "closed":
                new_state = "closed"

            conn.execute(
                "UPDATE ledger_meter SET spent=?, reserved=?, warned=?, state=? WHERE id=?",
                (
                    new_spent, new_reserved, 1 if (before.warned or crossed_warn) else 0,
                    new_state, meter_id,
                ),
            )
            sid = new_spend_id()
            conn.execute(
                "INSERT INTO ledger_spend_event (id, step_id, org_id, actuation_id, node_id, "
                "task_id, provider, model, input_tokens, output_tokens, est_cost_micros, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, step_id, org_id, actuation_id, node_id, task_id, provider, model,
                 int(input_tokens), int(output_tokens), int(est_cost_micros), ts),
            )
            mrow2 = conn.execute(
                "SELECT * FROM ledger_meter WHERE id = ?", (meter_id,)
            ).fetchone()

        return RecordOutcome(
            meter=_row_to_meter(mrow2),
            spendEvent=SpendEvent(
                id=sid, stepId=step_id, orgId=org_id, actuationId=actuation_id, nodeId=node_id,
                taskId=task_id, provider=provider, model=model, inputTokens=int(input_tokens),
                outputTokens=int(output_tokens), estCostMicros=int(est_cost_micros), createdAt=ts,
            ),
            crossedWarn=crossed_warn,
            exhausted=(new_state == "exhausted"),
        )

    def close_meter(self, meter_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE ledger_meter SET state='closed', closed_at=? WHERE id=?",
                (now_iso(), meter_id),
            )

    def raise_meter(self, meter_id: str, additional: int) -> Meter | None:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM ledger_meter WHERE id = ?", (meter_id,)
            ).fetchone()
            if row is None:
                return None
            m = _row_to_meter(row)
            new_allowance = m.allowance + max(0, additional)
            # Reopen if a top-up gives the meter room again.
            new_state = "open" if (m.state == "exhausted" and new_allowance > m.spent) else m.state
            conn.execute(
                "UPDATE ledger_meter SET allowance=?, state=? WHERE id=?",
                (new_allowance, new_state, meter_id),
            )
            row2 = conn.execute(
                "SELECT * FROM ledger_meter WHERE id = ?", (meter_id,)
            ).fetchone()
        return _row_to_meter(row2)

    def get_meter(self, meter_id: str) -> Meter | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM ledger_meter WHERE id = ?", (meter_id,)
            ).fetchone()
        return _row_to_meter(row) if row else None

    def rollup(self, org_id: str, group_by: str) -> list[dict]:
        column = {"node": "node_id", "task": "task_id", "model": "model"}.get(group_by)
        if column is None:
            raise ValueError(f"bad group_by {group_by!r} (node|task|model)")
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT {column} AS key, "  # noqa: S608 - column is from a fixed allowlist
                "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, "
                "SUM(est_cost_micros) AS est_cost_micros, COUNT(*) AS steps "
                "FROM ledger_spend_event WHERE org_id = ? GROUP BY key ORDER BY est_cost_micros "
                "DESC",
                (org_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def _spend_row_to_event(row) -> SpendEvent:
    return SpendEvent(
        id=row["id"],
        stepId=row["step_id"],
        orgId=row["org_id"],
        actuationId=row["actuation_id"],
        nodeId=row["node_id"],
        taskId=row["task_id"],
        provider=row["provider"],
        model=row["model"],
        inputTokens=row["input_tokens"],
        outputTokens=row["output_tokens"],
        estCostMicros=row["est_cost_micros"],
        createdAt=row["created_at"],
    )
