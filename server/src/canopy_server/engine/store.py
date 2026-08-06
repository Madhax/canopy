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
    new_cadence_id,
    new_deliverable_id,
    new_gate_id,
    new_intent_id,
    new_note_id,
    new_notification_id,
    new_plan_id,
    new_step_id,
    new_tool_event_id,
)
from .models import (
    ASSIGNMENT_TERMINAL_STATES,
    Assignment,
    Brief,
    Cadence,
    Deliverable,
    Gate,
    Intent,
    MemoryEntry,
    Note,
    Notification,
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
    meter_id        TEXT,
    priority        INTEGER NOT NULL DEFAULT 0,
    deliverable_id  TEXT,
    reassigned_from TEXT,
    session_ref     TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    closed_at       TEXT
);
CREATE INDEX IF NOT EXISTS ix_assignment_node   ON work_assignment (actuation_id, node_id, state);
-- Work belongs to the position (org+node), like agent_memory — the E6 re-actuation lookups.
CREATE INDEX IF NOT EXISTS ix_assignment_org_node ON work_assignment (org_id, node_id, state);
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
    started_at      TEXT,
    completed_at    TEXT,
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

CREATE TABLE IF NOT EXISTS work_note (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL,
    intent_id     TEXT NOT NULL,
    assignment_id TEXT,
    stage_idx     INTEGER,
    author        TEXT NOT NULL,
    text          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    delivered_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_note_intent ON work_note (intent_id, created_at);
CREATE INDEX IF NOT EXISTS ix_note_undelivered ON work_note (assignment_id)
    WHERE delivered_at IS NULL;

CREATE TABLE IF NOT EXISTS work_notification (
    id          TEXT PRIMARY KEY,
    org_id      TEXT NOT NULL,
    severity    TEXT NOT NULL,
    kind        TEXT NOT NULL,
    subject_ids TEXT NOT NULL DEFAULT '[]',
    dedupe_key  TEXT,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    read_at     TEXT
);
CREATE INDEX IF NOT EXISTS ix_notification_org ON work_notification (org_id, created_at);
-- One live notification per fact (e.g. budget-warn per assignment fires once).
CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_dedupe
    ON work_notification (org_id, kind, dedupe_key) WHERE dedupe_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS work_gate (
    id            TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    kind          TEXT NOT NULL,
    opened_by     TEXT NOT NULL,
    owner         TEXT NOT NULL,
    reason        TEXT NOT NULL,
    reason_hash   TEXT NOT NULL DEFAULT '',
    payload       TEXT NOT NULL DEFAULT '{}',
    state         TEXT NOT NULL DEFAULT 'open',
    resolution    TEXT,
    resolved_by   TEXT,
    created_at    TEXT NOT NULL,
    resolved_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_gate_open ON work_gate (state, owner);
CREATE INDEX IF NOT EXISTS ix_gate_assignment ON work_gate (assignment_id, state);
-- Trigger sweeps never double-open (engine.md §3): one open gate per (assignment, kind, reason).
CREATE UNIQUE INDEX IF NOT EXISTS ux_gate_open_dedupe
    ON work_gate (assignment_id, kind, reason_hash) WHERE state = 'open';

CREATE TABLE IF NOT EXISTS work_cadence (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL,
    node_id       TEXT,                        -- NULL ⇒ the org root at fire time
    name          TEXT NOT NULL,
    cron          TEXT NOT NULL,               -- five UTC fields (engine.md §4)
    intent_text   TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    last_fired_at TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cadence_org ON work_cadence (org_id, created_at);

CREATE TABLE IF NOT EXISTS work_tool_event (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL,
    actuation_id  TEXT NOT NULL,
    node_id       TEXT NOT NULL,
    assignment_id TEXT,
    tool          TEXT NOT NULL,
    params_hash   TEXT NOT NULL DEFAULT '',
    outcome       TEXT NOT NULL,               -- ok | denied | error
    detail        TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tool_event_node ON work_tool_event (actuation_id, node_id,
    created_at);
"""
register_schema(SCHEMA)


def _migrate_meter_nullable(db: Db) -> None:
    """E1 shipped ``work_assignment.meter_id NOT NULL``; staged delegation (E2) needs it nullable
    while ``proposed``. SQLite can't drop NOT NULL in place, so rebuild once for pre-E2 dev DBs.
    The new table DDL comes from SCHEMA via a temporary name so the definitions can't drift."""
    with db.connect() as conn:
        cols = conn.execute("PRAGMA table_info(work_assignment)").fetchall()
    meter_col = next((c for c in cols if c["name"] == "meter_id"), None)
    if meter_col is None or not meter_col["notnull"]:
        return
    ddl = SCHEMA.split("CREATE TABLE IF NOT EXISTS work_assignment", 1)[1].split(";", 1)[0]
    with db.transaction() as conn:
        conn.execute(f"CREATE TABLE work_assignment_new{ddl}")
        conn.execute("INSERT INTO work_assignment_new SELECT * FROM work_assignment")
        conn.execute("DROP TABLE work_assignment")
        conn.execute("ALTER TABLE work_assignment_new RENAME TO work_assignment")
        # The dropped table takes its indexes with it; recreate them.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_assignment_node "
            "ON work_assignment (actuation_id, node_id, state)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_assignment_intent ON work_assignment (intent_id)"
        )


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


def _cadence(r) -> Cadence:
    return Cadence(
        id=r["id"], orgId=r["org_id"], nodeId=r["node_id"], name=r["name"], cron=r["cron"],
        intentText=r["intent_text"], enabled=bool(r["enabled"]),
        lastFiredAt=r["last_fired_at"], createdAt=r["created_at"],
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
        startedAt=r["started_at"], completedAt=r["completed_at"],
    )


def _note(r) -> Note:
    return Note(
        id=r["id"], orgId=r["org_id"], intentId=r["intent_id"],
        assignmentId=r["assignment_id"], stageIdx=r["stage_idx"], author=r["author"],
        text=r["text"], createdAt=r["created_at"], deliveredAt=r["delivered_at"],
    )


def _notification(r) -> Notification:
    return Notification(
        id=r["id"], orgId=r["org_id"], severity=r["severity"], kind=r["kind"],
        subjectIds=json.loads(r["subject_ids"]), text=r["text"], createdAt=r["created_at"],
        readAt=r["read_at"],
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


def _gate(r) -> Gate:
    return Gate(
        id=r["id"], assignmentId=r["assignment_id"], kind=r["kind"], openedBy=r["opened_by"],
        owner=r["owner"], reason=r["reason"], payload=json.loads(r["payload"]), state=r["state"],
        resolution=json.loads(r["resolution"]) if r["resolution"] else None,
        resolvedBy=r["resolved_by"], createdAt=r["created_at"], resolvedAt=r["resolved_at"],
    )


def _migrate_stage_timestamps(db: Db) -> None:
    """E2b adds ``started_at``/``completed_at`` to work_plan_stage (amendment D-4). ALTER TABLE
    ADD COLUMN is safe for nullable columns; run once for pre-E2b dev DBs."""
    with db.connect() as conn:
        cols = {c["name"] for c in conn.execute("PRAGMA table_info(work_plan_stage)").fetchall()}
    if not cols or "started_at" in cols:
        return
    with db.transaction() as conn:
        conn.execute("ALTER TABLE work_plan_stage ADD COLUMN started_at TEXT")
        conn.execute("ALTER TABLE work_plan_stage ADD COLUMN completed_at TEXT")


class WorkStore:
    def __init__(self, db: Db):
        self.db = db
        _migrate_meter_nullable(db)
        _migrate_stage_timestamps(db)

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

    # ---------------------------------------------------------------- cadences
    def create_cadence(
        self, org_id: str, name: str, cron: str, intent_text: str, *,
        node_id: str | None = None, enabled: bool = True,
    ) -> Cadence:
        cid = new_cadence_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO work_cadence (id, org_id, node_id, name, cron, intent_text, "
                "enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, org_id, node_id, name, cron, intent_text, 1 if enabled else 0, ts),
            )
        return Cadence(
            id=cid, orgId=org_id, nodeId=node_id, name=name, cron=cron,
            intentText=intent_text, enabled=enabled, createdAt=ts,
        )

    def get_cadence(self, cadence_id: str) -> Cadence | None:
        with self.db.connect() as conn:
            r = conn.execute("SELECT * FROM work_cadence WHERE id=?", (cadence_id,)).fetchone()
        return _cadence(r) if r else None

    def list_cadences(
        self, org_id: str | None = None, *, enabled_only: bool = False,
    ) -> list[Cadence]:
        clauses, params = [], []
        if org_id is not None:
            clauses.append("org_id=?")
            params.append(org_id)
        if enabled_only:
            clauses.append("enabled=1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM work_cadence {where} ORDER BY created_at, id",  # noqa: S608
                params,
            ).fetchall()
        return [_cadence(r) for r in rows]

    def update_cadence(
        self, cadence_id: str, *, name: str | None = None, cron: str | None = None,
        intent_text: str | None = None, node_id: str | None = None, enabled: bool | None = None,
    ) -> Cadence | None:
        sets, params = [], []
        for col, val in (
            ("name", name), ("cron", cron), ("intent_text", intent_text), ("node_id", node_id),
            ("enabled", None if enabled is None else (1 if enabled else 0)),
        ):
            if val is not None:
                sets.append(f"{col}=?")
                params.append(val)
        if sets:
            with self.db.transaction() as conn:
                conn.execute(
                    f"UPDATE work_cadence SET {', '.join(sets)} WHERE id=?",  # noqa: S608
                    (*params, cadence_id),
                )
        return self.get_cadence(cadence_id)

    def mark_cadence_fired(self, cadence_id: str, ts: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE work_cadence SET last_fired_at=? WHERE id=?", (ts, cadence_id))

    def delete_cadence(self, cadence_id: str) -> None:
        """Delete the schedule only — intents it fired are ordinary history and stay."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM work_cadence WHERE id=?", (cadence_id,))

    def open_intent_for_cadence(self, cadence_id: str) -> Intent | None:
        """The still-open previous occurrence, if any — the misfire check (engine.md §4)."""
        with self.db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM work_intent WHERE cadence_id=? AND state='open' "
                "ORDER BY created_at DESC LIMIT 1",
                (cadence_id,),
            ).fetchone()
        return _intent(r) if r else None

    # ------------------------------------------------------------- assignments
    def create_assignment(
        self, *, org_id: str, actuation_id: str, intent_id: str, node_id: str, issued_by: str,
        contract_kind: str, contract_type: str, meter_id: str | None,
        parent_id: str | None = None, state: str = "created", priority: int = 0,
        reassigned_from: str | None = None, assignment_id: str | None = None,
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

    def current_assignment(self, org_id: str, node_id: str) -> Assignment | None:
        """The node's live assignment (most recent non-terminal). One `executing` per node is a
        domain rule, so at most one active row is expected — newest wins if a race leaves two.
        ``proposed`` drafts are excluded: nothing is published to the node until dispatch.

        Keyed by **org + node** (the position), not the actuation instance (E6): open work
        survives deactuate → re-actuate exactly like ``agent_memory`` — a fresh actuation
        doesn't orphan the org's in-flight assignments. ``actuation_id`` on the row stays as
        provenance (which actuation created it)."""
        hidden = sorted(ASSIGNMENT_TERMINAL_STATES | {"proposed"})
        placeholders = ",".join("?" for _ in hidden)
        with self.db.connect() as conn:
            r = conn.execute(
                "SELECT * FROM work_assignment WHERE org_id=? AND node_id=? "
                f"AND state NOT IN ({placeholders}) "  # noqa: S608 - fixed placeholders only
                "ORDER BY created_at DESC LIMIT 1",
                (org_id, node_id, *hidden),
            ).fetchone()
        return _assignment(r) if r else None

    def refs_granted_to(self, org_id: str, node_id: str) -> set[str]:
        """Every artifact ref granted to the node via any brief version of any of its
        assignments — the grant set the artifact fetch checks against (workspace.md §2: a
        manager can grant only refs it can itself read, so brief refs are transitively
        legitimate). Org+node keyed like ``current_assignment``: grants ride the position's
        briefs and survive re-actuation."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT b.artifact_refs FROM work_brief b "
                "JOIN work_assignment a ON a.id = b.assignment_id "
                "WHERE a.org_id=? AND a.node_id=?",
                (org_id, node_id),
            ).fetchall()
        refs: set[str] = set()
        for r in rows:
            refs.update(json.loads(r["artifact_refs"]))
        return refs

    def list_children(self, parent_id: str, *, state: str | None = None) -> list[Assignment]:
        params: list = [parent_id]
        extra = ""
        if state is not None:
            extra = "AND state=?"
            params.append(state)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM work_assignment WHERE parent_id=? {extra} "  # noqa: S608
                "ORDER BY created_at, id",
                params,
            ).fetchall()
        return [_assignment(r) for r in rows]

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

    def set_assignment_meter(self, assignment_id: str, meter_id: str) -> None:
        """Fund a proposed assignment at dispatch (work-model.md §2.1 staged delegation)."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_assignment SET meter_id=?, updated_at=? WHERE id=?",
                (meter_id, now_iso(), assignment_id),
            )

    def set_assignment_priority(self, assignment_id: str, priority: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_assignment SET priority=?, updated_at=? WHERE id=?",
                (priority, now_iso(), assignment_id),
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

    def amend_draft_brief(
        self, assignment_id: str, text: str, *, artifact_refs: list[str] | None = None,
    ) -> Brief | None:
        """Rewrite the draft (v1) brief in place. Only meaningful while the assignment is
        ``proposed`` — draft briefs stay mutable until dispatch; versioning starts at dispatch
        (work-model.md §2.1). The caller enforces the state precondition."""
        with self.db.transaction() as conn:
            if artifact_refs is None:
                conn.execute(
                    "UPDATE work_brief SET text=? WHERE assignment_id=? AND version=1",
                    (text, assignment_id),
                )
            else:
                conn.execute(
                    "UPDATE work_brief SET text=?, artifact_refs=? "
                    "WHERE assignment_id=? AND version=1",
                    (text, json.dumps(artifact_refs), assignment_id),
                )
        return self.get_brief(assignment_id, 1)

    def append_brief_refs(self, assignment_id: str, refs: list[str]) -> Brief | None:
        """Dependency resolution: append granted refs as a new system-attributed brief version
        (work-model.md §3 — exempt from the rework-funding rule)."""
        latest = self.get_brief(assignment_id)
        if latest is None:
            return None
        merged = list(dict.fromkeys([*latest.artifactRefs, *refs]))
        if merged == latest.artifactRefs:
            return latest  # idempotent under redelivery — nothing new to grant
        return self.add_brief(
            assignment_id, latest.text, artifact_refs=merged, revised_by="system",
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
        """Move a stage; stamps ``started_at`` on the first 'active' and ``completed_at`` on
        'done'/'dropped' (the plan timeline reads these — work-model.md §4)."""
        ts = now_iso()
        with self.db.transaction() as conn:
            if state == "active":
                conn.execute(
                    "UPDATE work_plan_stage SET state=?, "
                    "started_at=COALESCE(started_at, ?) WHERE plan_id=? AND idx=?",
                    (state, ts, plan_id, idx),
                )
            elif state in ("done", "dropped"):
                conn.execute(
                    "UPDATE work_plan_stage SET state=?, started_at=COALESCE(started_at, ?), "
                    "completed_at=? WHERE plan_id=? AND idx=?",
                    (state, ts, ts, plan_id, idx),
                )
            else:
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

    # ------------------------------------------------------------------- gates
    def create_gate(
        self, assignment_id: str, kind: str, *, opened_by: str, owner: str, reason: str,
        reason_hash: str, payload: dict,
    ) -> Gate:
        """Insert an open gate. Idempotent per (assignment, kind, reason-hash): if a matching open
        gate exists (the partial unique index), it is returned unchanged — sweeps never double-open
        (engine.md §3)."""
        gid = new_gate_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO work_gate (id, assignment_id, kind, opened_by, owner, "
                "reason, reason_hash, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (gid, assignment_id, kind, opened_by, owner, reason, reason_hash,
                 json.dumps(payload), ts),
            )
            if cur.rowcount == 0:  # lost to the dedupe index — hand back the existing open gate
                r = conn.execute(
                    "SELECT * FROM work_gate WHERE assignment_id=? AND kind=? AND reason_hash=? "
                    "AND state='open'",
                    (assignment_id, kind, reason_hash),
                ).fetchone()
                return _gate(r)
        return Gate(
            id=gid, assignmentId=assignment_id, kind=kind, openedBy=opened_by, owner=owner,
            reason=reason, payload=payload, state="open", createdAt=ts,
        )

    def get_gate(self, gate_id: str) -> Gate | None:
        with self.db.connect() as conn:
            r = conn.execute("SELECT * FROM work_gate WHERE id=?", (gate_id,)).fetchone()
        return _gate(r) if r else None

    def list_gates(
        self, *, assignment_id: str | None = None, kind: str | None = None,
        state: str | None = None, owner: str | None = None, org_id: str | None = None,
    ) -> list[Gate]:
        clauses, params = [], []
        for col, val in (
            ("g.assignment_id", assignment_id), ("g.kind", kind), ("g.state", state),
            ("g.owner", owner),
        ):
            if val is not None:
                clauses.append(f"{col}=?")
                params.append(val)
        join = ""
        if org_id is not None:  # the operator inbox filters by org via the assignment
            join = "JOIN work_assignment a ON a.id = g.assignment_id"
            clauses.append("a.org_id=?")
            params.append(org_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT g.* FROM work_gate g {join} {where} "  # noqa: S608 - fixed columns only
                "ORDER BY g.created_at, g.id",
                params,
            ).fetchall()
        return [_gate(r) for r in rows]

    def update_gate_payload(self, gate_id: str, payload: dict) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_gate SET payload=? WHERE id=?", (json.dumps(payload), gate_id)
            )

    def resolve_gate(
        self, gate_id: str, *, resolution: dict, resolved_by: str, state: str = "resolved",
    ) -> Gate | None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE work_gate SET state=?, resolution=?, resolved_by=?, resolved_at=? "
                "WHERE id=? AND state='open'",
                (state, json.dumps(resolution), resolved_by, now_iso(), gate_id),
            )
        return self.get_gate(gate_id)

    # ------------------------------------------------------------------- notes
    def create_note(
        self, org_id: str, intent_id: str, text: str, *, assignment_id: str | None = None,
        stage_idx: int | None = None, author: str = "operator",
    ) -> Note:
        nid = new_note_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO work_note (id, org_id, intent_id, assignment_id, stage_idx, "
                "author, text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (nid, org_id, intent_id, assignment_id, stage_idx, author, text, ts),
            )
        return Note(
            id=nid, orgId=org_id, intentId=intent_id, assignmentId=assignment_id,
            stageIdx=stage_idx, author=author, text=text, createdAt=ts,
        )

    def list_notes(self, intent_id: str) -> list[Note]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM work_note WHERE intent_id=? ORDER BY created_at, id", (intent_id,)
            ).fetchall()
        return [_note(r) for r in rows]

    def take_undelivered_notes(self, assignment_id: str) -> list[Note]:
        """The assignment's undelivered notes, stamped ``delivered_at`` in the same transaction —
        a note is injected exactly once (amendment D-5)."""
        ts = now_iso()
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM work_note WHERE assignment_id=? AND delivered_at IS NULL "
                "ORDER BY created_at, id",
                (assignment_id,),
            ).fetchall()
            if rows:
                conn.execute(
                    "UPDATE work_note SET delivered_at=? "
                    "WHERE assignment_id=? AND delivered_at IS NULL",
                    (ts, assignment_id),
                )
        notes = [_note(r) for r in rows]
        for n in notes:
            n.deliveredAt = ts
        return notes

    # ----------------------------------------------------------- notifications
    def notify(
        self, org_id: str, severity: str, kind: str, text: str, *,
        subject_ids: list[str] | None = None, dedupe_key: str | None = None,
    ) -> Notification | None:
        """Insert a notification. With ``dedupe_key``, a duplicate of a live fact is dropped
        (partial unique index) and None is returned — budget-warn per assignment fires once."""
        nid = new_notification_id()
        ts = now_iso()
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO work_notification (id, org_id, severity, kind, "
                "subject_ids, dedupe_key, text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (nid, org_id, severity, kind, json.dumps(subject_ids or []), dedupe_key,
                 text, ts),
            )
            if cur.rowcount == 0:
                return None
        return Notification(
            id=nid, orgId=org_id, severity=severity, kind=kind, subjectIds=subject_ids or [],
            text=text, createdAt=ts,
        )

    def list_notifications(
        self, org_id: str, *, since: str | None = None, unread_only: bool = False,
    ) -> list[Notification]:
        clauses, params = ["org_id=?"], [org_id]
        if since is not None:
            clauses.append("created_at > ?")
            params.append(since)
        if unread_only:
            clauses.append("read_at IS NULL")
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM work_notification WHERE {' AND '.join(clauses)} "  # noqa: S608
                "ORDER BY created_at, id",
                params,
            ).fetchall()
        return [_notification(r) for r in rows]

    def mark_notifications_read(self, org_id: str, ids: list[str] | None = None) -> int:
        """Mark the given notifications read (or all unread for the org). Returns the count."""
        ts = now_iso()
        with self.db.transaction() as conn:
            if ids:
                placeholders = ",".join("?" for _ in ids)
                cur = conn.execute(
                    f"UPDATE work_notification SET read_at=? WHERE org_id=? "  # noqa: S608
                    f"AND read_at IS NULL AND id IN ({placeholders})",
                    (ts, org_id, *ids),
                )
            else:
                cur = conn.execute(
                    "UPDATE work_notification SET read_at=? WHERE org_id=? AND read_at IS NULL",
                    (ts, org_id),
                )
        return cur.rowcount

    def list_gates_for_node(self, org_id: str, node_id: str, *, limit: int = 100) -> list[Gate]:
        """All gates on one node's assignments, newest first — the inspector's Gates tab
        (open + historical in one query; the route partitions)."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT g.* FROM work_gate g "
                "JOIN work_assignment a ON a.id = g.assignment_id "
                "WHERE a.org_id = ? AND a.node_id = ? "
                "ORDER BY g.created_at DESC, g.id DESC LIMIT ?",
                (org_id, node_id, limit),
            ).fetchall()
        return [_gate(r) for r in rows]

    # ------------------------------------------------------------ events (SSE)
    def change_watermark(self, org_id: str) -> dict[str, tuple]:
        """Cheap per-org change counters for the /events channel (engine.md §6). The SSE tailer
        diffs consecutive snapshots and emits one coalesced event per changed family — steps at
        10/s become at most one event per tick, and stage/note/notification *stamps* (updates
        that fill a nullable column) register without any engine-side hooks. Every counter only
        ever grows, so tuple equality means "nothing happened"."""
        with self.db.connect() as conn:
            step = conn.execute(
                "SELECT COUNT(*) AS n FROM work_step s "
                "JOIN work_assignment a ON a.id = s.assignment_id WHERE a.org_id = ?",
                (org_id,),
            ).fetchone()
            plan = conn.execute(
                "SELECT COUNT(*) AS n, COUNT(ps.started_at) AS started, "
                "COUNT(ps.completed_at) AS completed FROM work_plan_stage ps "
                "JOIN work_plan p ON p.id = ps.plan_id "
                "JOIN work_assignment a ON a.id = p.assignment_id WHERE a.org_id = ?",
                (org_id,),
            ).fetchone()
            note = conn.execute(
                "SELECT COUNT(*) AS n, COUNT(delivered_at) AS delivered "
                "FROM work_note WHERE org_id = ?",
                (org_id,),
            ).fetchone()
            notif = conn.execute(
                "SELECT COUNT(*) AS n, COUNT(read_at) AS read "
                "FROM work_notification WHERE org_id = ?",
                (org_id,),
            ).fetchone()
        return {
            "steps": (step["n"],),
            "plan": (plan["n"], plan["started"], plan["completed"]),
            "notes": (note["n"], note["delivered"]),
            "notifications": (notif["n"], notif["read"]),
        }

    # ------------------------------------------------------------- tool events
    def record_tool_event(
        self, *, org_id: str, actuation_id: str, node_id: str, tool: str, outcome: str,
        assignment_id: str | None = None, params_hash: str = "", detail: str = "",
    ) -> str:
        """The observability record for every MCP/tool invocation (envelope §3.4) — including
        the denied ones, which is the point: a hallucinated call is visible, not silent."""
        tid = new_tool_event_id()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO work_tool_event (id, org_id, actuation_id, node_id, assignment_id, "
                "tool, params_hash, outcome, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, org_id, actuation_id, node_id, assignment_id, tool, params_hash, outcome,
                 detail, now_iso()),
            )
        return tid

    def list_tool_events(self, actuation_id: str, node_id: str) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM work_tool_event WHERE actuation_id=? AND node_id=? "
                "ORDER BY created_at, id",
                (actuation_id, node_id),
            ).fetchall()
        return [dict(r) for r in rows]
