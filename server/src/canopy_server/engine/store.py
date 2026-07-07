"""WorkStore — the persistence layer for the work model (work-model.md).

Owns the ``work_*`` tables and ``agent_memory`` (topology rule 2: one owner-module per table
family). Pure storage: it versions briefs and plans, moves assignment rows between states, appends
steps and deliverables, and keeps durable per-node memory. It does *not* fund meters, route
messages, or decide transitions — that judgment is the :class:`ExecutionEngine`'s (engine.md §1).

Conventions mirror the rest of the server: fresh connection per operation, ``BEGIN IMMEDIATE`` for
multi-statement writes, camelCase Pydantic out / snake_case rows in, ids from ``ids.py``. JSON-
shaped columns (artifact refs, attestations, memory entries) are stored as text and parsed at the
boundary.
"""

from __future__ import annotations

import json

from ..db import Db, register_schema
from ..deps import now_iso
from ..ids import (
    new_assignment_id,
    new_deliverable_id,
    new_intent_id,
    new_plan_id,
    new_step_id,
)
from .models import (
    ASSIGNMENT_TERMINAL_STATES,
    Assignment,
    Brief,
    Deliverable,
    Intent,
    MemoryEntry,
    Plan,
    PlanStage,
    Step,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS work_intent (
    id                 TEXT PRIMARY KEY,
    org_id             TEXT NOT NULL,
    actuation_id       TEXT NOT NULL,
    target_node        TEXT NOT NULL,
    kind               TEXT NOT NULL DEFAULT 'episodic',
    text               TEXT NOT NULL,
    state              TEXT NOT NULL DEFAULT 'open',
    root_assignment_id TEXT,
    cadence_id         TEXT,
    created_by         TEXT NOT NULL DEFAULT 'operator',
    created_at         TEXT NOT NULL,
    closed_at          TEXT
);
CREATE INDEX IF NOT EXISTS ix_intent_org ON work_intent (org_id, created_at);

CREATE TABLE IF NOT EXISTS work_assignment (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL,
    actuation_id    TEXT NOT NULL,
    intent_id       TEXT NOT NULL,
    parent_id       TEXT,
    node_id         TEXT NOT NULL,
    issued_by       TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'created',
    brief_version   INTEGER NOT NULL DEFAULT 1,
    contract_kind   TEXT NOT NULL,
    contract_type   TEXT NOT NULL,
    meter_id        TEXT NOT NULL,
    priority        INTEGER NOT NULL DEFAULT 0,
    deliverable_id  TEXT,
    reassigned_from TEXT,
    session_ref     TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    closed_at       TEXT
);
CREATE INDEX IF NOT EXISTS ix_assignment_node   ON work_assignment (actuation_id, node_id, state);
CREATE INDEX IF NOT EXISTS ix_assignment_intent ON work_assignment (intent_id);

CREATE TABLE IF NOT EXISTS work_brief (
    assignment_id TEXT NOT NULL,
    version       INTEGER NOT NULL,
    text          TEXT NOT NULL,
    artifact_refs TEXT NOT NULL DEFAULT '[]',
    revised_by    TEXT,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (assignment_id, version)
);

CREATE TABLE IF NOT EXISTS work_plan (
    id            TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_plan_assignment ON work_plan (assignment_id, version);

CREATE TABLE IF NOT EXISTS work_plan_stage (
    plan_id         TEXT NOT NULL,
    idx             INTEGER NOT NULL,
    title           TEXT NOT NULL,
    completion      TEXT NOT NULL DEFAULT '',
    sizing          TEXT NOT NULL DEFAULT 'medium',
    envelope_tokens INTEGER,
    state           TEXT NOT NULL DEFAULT 'pending',
    PRIMARY KEY (plan_id, idx)
);

CREATE TABLE IF NOT EXISTS work_step (
    id              TEXT PRIMARY KEY,
    assignment_id   TEXT NOT NULL,
    stage_idx       INTEGER,
    session_span_id TEXT,
    kind            TEXT NOT NULL DEFAULT 'production',
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL,
    delta_kind      TEXT NOT NULL DEFAULT 'none',
    delta_ref       TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_step_assignment ON work_step (assignment_id, created_at);

CREATE TABLE IF NOT EXISTS work_deliverable (
    id            TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    kind          TEXT NOT NULL,
    artifact_refs TEXT NOT NULL DEFAULT '[]',
    attestation   TEXT,
    summary       TEXT NOT NULL DEFAULT '',
    accepted      INTEGER,
    review_note   TEXT,
    created_at    TEXT NOT NULL,
    reviewed_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_deliverable_assignment ON work_deliverable (assignment_id);

CREATE TABLE IF NOT EXISTS agent_memory (
    org_id     TEXT NOT NULL,
    node_id    TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    entry      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (org_id, node_id, seq)
);
"""
register_schema(SCHEMA)


# --------------------------------------------------------------------------- #
# Row → model mappers
# --------------------------------------------------------------------------- #
def _intent(r) -> Intent:
    return Intent(
        id=r["id"], orgId=r["org_id"], actuationId=r["actuation_id"], targetNode=r["target_node"],
        kind=r["kind"], text=r["text"], state=r["state"],
        rootAssignmentId=r["root_assignment_id"], cadenceId=r["cadence_id"],
        createdBy=r["created_by"], createdAt=r["created_at"], closedAt=r["closed_at"],
    )


def _assignment(r) -> Assignment:
    return Assignment(
        id=r["id"], orgId=r["org_id"], actuationId=r["actuation_id"], intentId=r["intent_id"],
        parentId=r["parent_id"], nodeId=r["node_id"], issuedBy=r["issued_by"], state=r["state"],
        briefVersion=r["brief_version"], contractKind=r["contract_kind"],
        contractType=r["contract_type"], meterId=r["meter_id"], priority=r["priority"],
        deliverableId=r["deliverable_id"], reassignedFrom=r["reassigned_from"],
        sessionRef=r["session_ref"], createdAt=r["created_at"], updatedAt=r["updated_at"],
        closedAt=r["closed_at"],
    )


def _brief(r) -> Brief:
    return Brief(
        assignmentId=r["assignment_id"], version=r["version"], text=r["text"],
        artifactRefs=json.loads(r["artifact_refs"]), revisedBy=r["revised_by"],
        createdAt=r["created_at"],
    )


def _stage(r) -> PlanStage:
    return PlanStage(
        planId=r["plan_id"], idx=r["idx"], title=r["title"], completion=r["completion"],
        sizing=r["sizing"], envelopeTokens=r["envelope_tokens"], state=r["state"],
    )


def _step(r) -> Step:
    return Step(
        id=r["id"], assignmentId=r["assignment_id"], stageIdx=r["stage_idx"],
        sessionSpanId=r["session_span_id"], kind=r["kind"], inputTokens=r["input_tokens"],
        outputTokens=r["output_tokens"], durationMs=r["duration_ms"], deltaKind=r["delta_kind"],
        deltaRef=r["delta_ref"], createdAt=r["created_at"],
    )


def _deliverable(r) -> Deliverable:
    accepted = None if r["accepted"] is None else bool(r["accepted"])
    return Deliverable(
        id=r["id"], assignmentId=r["assignment_id"], kind=r["kind"],
        artifactRefs=json.loads(r["artifact_refs"]),
        attestation=json.loads(r["attestation"]) if r["attestation"] else None,
        summary=r["summary"], accepted=accepted, reviewNote=r["review_note"],
        createdAt=r["created_at"], reviewedAt=r["reviewed_at"],
    )


def _memory(r) -> MemoryEntry:
    return MemoryEntry(
        orgId=r["org_id"], nodeId=r["node_id"], seq=r["seq"], entry=json.loads(r["entry"]),
        createdAt=r["created_at"],
    )


class WorkStore:
    def __init__(self, db: Db):
        self.db = db

    # ----------------------------------------------------------------- intents
    def create_intent(
        self, org_id: str, actuation_id: str, target_node: str, text: str, *,
        kind: str = "episodic", created_by: str = "operator", cadence_id: str | None = None,
    ) -> Intent:
        iid = new_intent_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO work_intent (id, org_id, actuation_id, target_node, kind, text, "
                "cadence_id, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (iid, org_id, actuation_id, target_node, kind, text, cadence_id, created_by, ts),
            )
        return Intent(
            id=iid, orgId=org_id, actuationId=actuation_id, targetNode=target_node, kind=kind,
            text=text, state="open", cadenceId=cadence_id, createdBy=created_by, createdAt=ts,
        )

    def get_intent(self, intent_id: str) -> Intent | None:
        with self.db.connect() as conn:
            r = conn.execute("SELECT * FROM work_intent WHERE id=?", (intent_id,)).fetchone()
        return _intent(r) if r else None

    def list_intents(self, org_id: str) -> list[Intent]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM work_intent WHERE org_id=? ORDER BY created_at DESC", (org_id,)
            ).fetchall()
        return [_intent(r) for r in rows]

    def set_intent_root(self, intent_id: str, root_assignment_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_intent SET root_assignment_id=? WHERE id=?",
                (root_assignment_id, intent_id),
            )

    def close_intent(self, intent_id: str, state: str) -> None:
        """Close an episodic intent (``completed`` | ``failed`` | ``cancelled``)."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_intent SET state=?, closed_at=? WHERE id=?",
                (state, now_iso(), intent_id),
            )

    # ------------------------------------------------------------- assignments
    def create_assignment(
        self, *, org_id: str, actuation_id: str, intent_id: str, node_id: str, issued_by: str,
        contract_kind: str, contract_type: str, meter_id: str, parent_id: str | None = None,
        state: str = "created", priority: int = 0, reassigned_from: str | None = None,
        assignment_id: str | None = None,
    ) -> Assignment:
        aid = assignment_id or new_assignment_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO work_assignment (id, org_id, actuation_id, intent_id, parent_id, "
                "node_id, issued_by, state, contract_kind, contract_type, meter_id, priority, "
                "reassigned_from, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (aid, org_id, actuation_id, intent_id, parent_id, node_id, issued_by, state,
                 contract_kind, contract_type, meter_id, priority, reassigned_from, ts, ts),
            )
        return Assignment(
            id=aid, orgId=org_id, actuationId=actuation_id, intentId=intent_id, parentId=parent_id,
            nodeId=node_id, issuedBy=issued_by, state=state, briefVersion=1,
            contractKind=contract_kind, contractType=contract_type, meterId=meter_id,
            priority=priority, reassignedFrom=reassigned_from, createdAt=ts, updatedAt=ts,
        )

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        with self.db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM work_assignment WHERE id=?", (assignment_id,)
            ).fetchone()
        return _assignment(r) if r else None

    def current_assignment(self, actuation_id: str, node_id: str) -> Assignment | None:
        """The node's live assignment (most recent non-terminal). One `executing` per node is a
        domain rule, so at most one active row is expected — newest wins if a race leaves two."""
        placeholders = ",".join("?" for _ in ASSIGNMENT_TERMINAL_STATES)
        with self.db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM work_assignment WHERE actuation_id=? AND node_id=? "
                f"AND state NOT IN ({placeholders}) "  # noqa: S608 - fixed placeholders only
                "ORDER BY created_at DESC LIMIT 1",
                (actuation_id, node_id, *sorted(ASSIGNMENT_TERMINAL_STATES)),
            ).fetchone()
        return _assignment(r) if r else None

    def list_assignments(
        self, *, org_id: str | None = None, actuation_id: str | None = None,
        node_id: str | None = None, state: str | None = None, intent_id: str | None = None,
    ) -> list[Assignment]:
        clauses, params = [], []
        for col, val in (
            ("org_id", org_id), ("actuation_id", actuation_id), ("node_id", node_id),
            ("state", state), ("intent_id", intent_id),
        ):
            if val is not None:
                clauses.append(f"{col}=?")
                params.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM work_assignment {where} ORDER BY created_at",  # noqa: S608
                params,
            ).fetchall()
        return [_assignment(r) for r in rows]

    def set_assignment_state(self, assignment_id: str, state: str) -> None:
        ts = now_iso()
        closed = ts if state in ASSIGNMENT_TERMINAL_STATES else None
        with self.db.transaction() as conn:
            if closed is not None:
                conn.execute(
                    "UPDATE work_assignment SET state=?, updated_at=?, closed_at=? WHERE id=?",
                    (state, ts, closed, assignment_id),
                )
            else:
                conn.execute(
                    "UPDATE work_assignment SET state=?, updated_at=? WHERE id=?",
                    (state, ts, assignment_id),
                )

    def set_deliverable_ref(self, assignment_id: str, deliverable_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_assignment SET deliverable_id=?, updated_at=? WHERE id=?",
                (deliverable_id, now_iso(), assignment_id),
            )

    def set_session_ref(self, assignment_id: str, session_ref: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_assignment SET session_ref=?, updated_at=? WHERE id=?",
                (session_ref, now_iso(), assignment_id),
            )

    # ------------------------------------------------------------------ briefs
    def add_brief(
        self, assignment_id: str, text: str, *, artifact_refs: list[str] | None = None,
        revised_by: str | None = None,
    ) -> Brief:
        """Append the next brief version and stamp it on the assignment (rework funds off this)."""
        refs = json.dumps(artifact_refs or [])
        ts = now_iso()
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM work_brief WHERE assignment_id=?", (assignment_id,)
            ).fetchone()
            version = (row["v"] or 0) + 1
            conn.execute(
                "INSERT INTO work_brief (assignment_id, version, text, artifact_refs, revised_by, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (assignment_id, version, text, refs, revised_by, ts),
            )
            conn.execute(
                "UPDATE work_assignment SET brief_version=?, updated_at=? WHERE id=?",
                (version, ts, assignment_id),
            )
        return Brief(
            assignmentId=assignment_id, version=version, text=text,
            artifactRefs=artifact_refs or [], revisedBy=revised_by, createdAt=ts,
        )

    def get_brief(self, assignment_id: str, version: int | None = None) -> Brief | None:
        with self.db.connect() as conn:
            if version is None:
                r = conn.execute(
                    "SELECT * FROM work_brief WHERE assignment_id=? ORDER BY version DESC LIMIT 1",
                    (assignment_id,),
                ).fetchone()
            else:
                r = conn.execute(
                    "SELECT * FROM work_brief WHERE assignment_id=? AND version=?",
                    (assignment_id, version),
                ).fetchone()
        return _brief(r) if r else None

    def list_briefs(self, assignment_id: str) -> list[Brief]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM work_brief WHERE assignment_id=? ORDER BY version",
                (assignment_id,),
            ).fetchall()
        return [_brief(r) for r in rows]

    # ------------------------------------------------------------------- plans
    def create_plan(self, assignment_id: str, stages: list[dict]) -> Plan:
        """Store a new (versioned) plan and its stages. ``stages`` items: ``{title, completion?,
        sizing?, envelopeTokens?}``."""
        pid = new_plan_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM work_plan WHERE assignment_id=?", (assignment_id,)
            ).fetchone()
            version = (row["v"] or 0) + 1
            conn.execute(
                "INSERT INTO work_plan (id, assignment_id, version, created_at) "
                "VALUES (?, ?, ?, ?)",
                (pid, assignment_id, version, ts),
            )
            for idx, s in enumerate(stages):
                conn.execute(
                    "INSERT INTO work_plan_stage (plan_id, idx, title, completion, sizing, "
                    "envelope_tokens, state) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                    (pid, idx, s["title"], s.get("completion", ""), s.get("sizing", "medium"),
                     s.get("envelopeTokens")),
                )
        return self.get_plan(assignment_id, version)  # type: ignore[return-value]

    def get_plan(self, assignment_id: str, version: int | None = None) -> Plan | None:
        with self.db.connect() as conn:
            if version is None:
                pr = conn.execute(
                    "SELECT * FROM work_plan WHERE assignment_id=? ORDER BY version DESC LIMIT 1",
                    (assignment_id,),
                ).fetchone()
            else:
                pr = conn.execute(
                    "SELECT * FROM work_plan WHERE assignment_id=? AND version=?",
                    (assignment_id, version),
                ).fetchone()
            if pr is None:
                return None
            stages = conn.execute(
                "SELECT * FROM work_plan_stage WHERE plan_id=? ORDER BY idx", (pr["id"],)
            ).fetchall()
        return Plan(
            id=pr["id"], assignmentId=pr["assignment_id"], version=pr["version"],
            createdAt=pr["created_at"], stages=[_stage(s) for s in stages],
        )

    def set_stage_state(self, plan_id: str, idx: int, state: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_plan_stage SET state=? WHERE plan_id=? AND idx=?",
                (state, plan_id, idx),
            )

    # ------------------------------------------------------------------- steps
    def add_step(
        self, assignment_id: str, *, input_tokens: int, output_tokens: int, duration_ms: int,
        kind: str = "production", stage_idx: int | None = None, session_span_id: str | None = None,
        delta_kind: str = "none", delta_ref: str | None = None, step_id: str | None = None,
    ) -> Step:
        """Record an observed Step. ``step_id`` may carry the gateway's SpendEvent id so the
        observability row and the money row share one id (the unified Step) and a redelivered
        report dedupes on the primary key (``INSERT OR IGNORE`` — engine.md §8)."""
        sid = step_id or new_step_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO work_step (id, assignment_id, stage_idx, session_span_id, "
                "kind, input_tokens, output_tokens, duration_ms, delta_kind, delta_ref, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, assignment_id, stage_idx, session_span_id, kind, int(input_tokens),
                 int(output_tokens), int(duration_ms), delta_kind, delta_ref, ts),
            )
        return Step(
            id=sid, assignmentId=assignment_id, stageIdx=stage_idx, sessionSpanId=session_span_id,
            kind=kind, inputTokens=int(input_tokens), outputTokens=int(output_tokens),
            durationMs=int(duration_ms), deltaKind=delta_kind, deltaRef=delta_ref, createdAt=ts,
        )

    def list_steps(self, assignment_id: str) -> list[Step]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM work_step WHERE assignment_id=? ORDER BY created_at, id",
                (assignment_id,),
            ).fetchall()
        return [_step(r) for r in rows]

    # ------------------------------------------------------------ deliverables
    def create_deliverable(
        self, assignment_id: str, kind: str, *, artifact_refs: list[str] | None = None,
        attestation: dict | None = None, summary: str = "",
    ) -> Deliverable:
        did = new_deliverable_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO work_deliverable (id, assignment_id, kind, artifact_refs, "
                "attestation, summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (did, assignment_id, kind, json.dumps(artifact_refs or []),
                 json.dumps(attestation) if attestation is not None else None, summary, ts),
            )
        return Deliverable(
            id=did, assignmentId=assignment_id, kind=kind, artifactRefs=artifact_refs or [],
            attestation=attestation, summary=summary, accepted=None, reviewNote=None, createdAt=ts,
        )

    def get_deliverable(self, deliverable_id: str) -> Deliverable | None:
        with self.db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM work_deliverable WHERE id=?", (deliverable_id,)
            ).fetchone()
        return _deliverable(r) if r else None

    def review_deliverable(
        self, deliverable_id: str, accepted: bool, note: str | None = None
    ) -> Deliverable | None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_deliverable SET accepted=?, review_note=?, reviewed_at=? WHERE id=?",
                (1 if accepted else 0, note, now_iso(), deliverable_id),
            )
            r = conn.execute(
                "SELECT * FROM work_deliverable WHERE id=?", (deliverable_id,)
            ).fetchone()
        return _deliverable(r) if r else None

    # ------------------------------------------------------------------ memory
    def append_memory(self, org_id: str, node_id: str, entry: dict) -> MemoryEntry:
        """Append a durable memory entry (engine writes one at assignment close). Keyed by
        org+node so it survives re-actuation — deactuation doesn't lobotomize the org's people."""
        ts = now_iso()
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT MAX(seq) AS s FROM agent_memory WHERE org_id=? AND node_id=?",
                (org_id, node_id),
            ).fetchone()
            seq = (row["s"] or 0) + 1
            conn.execute(
                "INSERT INTO agent_memory (org_id, node_id, seq, entry, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (org_id, node_id, seq, json.dumps(entry), ts),
            )
        return MemoryEntry(orgId=org_id, nodeId=node_id, seq=seq, entry=entry, createdAt=ts)

    def get_memory(self, org_id: str, node_id: str, limit: int = 20) -> list[MemoryEntry]:
        """The node's most recent entries, oldest → newest (the "your recent work" block)."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_memory WHERE org_id=? AND node_id=? "
                "ORDER BY seq DESC LIMIT ?",
                (org_id, node_id, limit),
            ).fetchall()
        return [_memory(r) for r in reversed(rows)]

    def reset_memory(self, org_id: str, node_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM agent_memory WHERE org_id=? AND node_id=?", (org_id, node_id)
            )
