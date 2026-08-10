"""Work-layer boundary shapes and state enums (work-model.md).

camelCase Pydantic at the boundary, snake_case in SQLite (the store maps between them). These are
the domain's objects made concrete: Intent → Assignment → Brief / Plan / Step → Deliverable, plus
durable per-node Memory. State machines live here as ``Literal`` sets so both the store and the
engine share one source of truth for "what states exist".
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# State enums (the domain's, verbatim — work-model.md §1, §2.1, §4, §5).
# --------------------------------------------------------------------------- #
IntentKind = Literal["episodic", "standing"]
IntentState = Literal["open", "completed", "failed", "cancelled"]

AssignmentState = Literal[
    "created", "proposed", "briefed", "intake", "planning", "executing", "delivering",
    "accepted", "rejected", "closed", "gated", "paused", "cancelled", "failed",
]
#: Assignment is live work — a runtime may be driving it or it may be waiting on a gate/hold.
#: ``proposed`` is deliberately NOT active: an unfunded draft is invisible to its node until
#: the plan-review approval dispatches it (work-model.md §2.1, staged delegation).
ASSIGNMENT_ACTIVE_STATES: frozenset[str] = frozenset({
    "created", "briefed", "intake", "planning", "executing", "delivering", "rejected",
    "gated", "paused",
})
#: Nothing more happens; the row is history.
ASSIGNMENT_TERMINAL_STATES: frozenset[str] = frozenset({
    "accepted", "closed", "cancelled", "failed",
})

GateKind = Literal["clarification", "dependency", "approval", "escalation", "intervention"]
GateState = Literal["open", "resolved", "expired"]

ContractKind = Literal["artifact", "attestation"]
DeliverableKind = Literal["artifact", "attestation"]

StepKind = Literal["coordination", "production"]  # SC-1 metric (kept from A1)
DeltaKind = Literal["artifact", "tool-effect", "progress", "message", "none"]  # closed enum (D6)

PlanStageState = Literal["pending", "active", "done", "dropped"]
Sizing = Literal["small", "medium", "large"]


# --------------------------------------------------------------------------- #
# Objects
# --------------------------------------------------------------------------- #
class Intent(BaseModel):
    id: str
    teamId: str
    actuationId: str
    targetNode: str
    kind: IntentKind
    text: str
    state: IntentState
    rootAssignmentId: str | None = None
    cadenceId: str | None = None
    createdBy: str
    createdAt: str
    closedAt: str | None = None
    # Trigger provenance (standing-teams.md §3): the ⚡ chip and the dedupe key.
    triggerId: str | None = None
    externalKey: str | None = None


class Assignment(BaseModel):
    id: str
    teamId: str
    actuationId: str
    intentId: str
    parentId: str | None
    nodeId: str
    issuedBy: str
    state: AssignmentState
    briefVersion: int
    contractKind: ContractKind
    contractType: str
    meterId: str | None  # NULL only while 'proposed' — funded at dispatch (work-model.md §2)
    priority: int
    deliverableId: str | None = None
    reassignedFrom: str | None = None
    sessionRef: str | None = None
    createdAt: str
    updatedAt: str
    closedAt: str | None = None
    # F14: runtime-reported liveness. None = a non-reporting runtime (loop); triggers then
    # fall back to step inference.
    lastActivityAt: str | None = None
    sessionHealth: str | None = None  # running | erroring
    sessionHealthDetail: str | None = None
    # F16: where the CLI writes this assignment's conversation transcript (adapter-reported
    # pointer; the adapter also archives a copy under the assignment's work home at exit).
    transcriptPath: str | None = None


class Brief(BaseModel):
    assignmentId: str
    version: int
    text: str
    artifactRefs: list[str]
    revisedBy: str | None
    createdAt: str


class PlanStage(BaseModel):
    planId: str
    idx: int
    title: str
    completion: str
    sizing: Sizing
    envelopeTokens: int | None
    state: PlanStageState
    startedAt: str | None = None  # stamped on first transition to 'active' (plan timeline, D-4)
    completedAt: str | None = None  # stamped on 'done' | 'dropped'


class Plan(BaseModel):
    id: str
    assignmentId: str
    version: int
    createdAt: str
    stages: list[PlanStage]


class Step(BaseModel):
    id: str
    assignmentId: str
    stageIdx: int | None
    sessionSpanId: str | None
    kind: StepKind
    inputTokens: int
    outputTokens: int
    # F1: the cached context window, settled separately so the ledger sees real consumption.
    cacheReadTokens: int = 0
    cacheCreationTokens: int = 0
    durationMs: int
    deltaKind: DeltaKind
    deltaRef: str | None
    createdAt: str


class Deliverable(BaseModel):
    id: str
    assignmentId: str
    kind: DeliverableKind
    artifactRefs: list[str]
    attestation: dict[str, Any] | None
    summary: str
    accepted: bool | None  # None pending, True accepted, False rejected
    reviewNote: str | None
    createdAt: str
    reviewedAt: str | None = None


class Note(BaseModel):
    """The advice channel (amendment D-5): anchored, non-blocking, injected at the next turn
    boundary. Opens no gate, revises no brief, constrains nothing."""

    id: str
    teamId: str
    intentId: str
    assignmentId: str | None = None  # None ⇒ a note on the intent itself
    stageIdx: int | None = None
    author: str
    text: str
    createdAt: str
    deliveredAt: str | None = None


NotificationSeverity = Literal["attention", "warning", "info"]


class Notification(BaseModel):
    id: str
    teamId: str
    severity: NotificationSeverity
    kind: str  # gate-waiting | budget-warn | hard-stop | stall | intent-completed | ...
    subjectIds: list[str]
    text: str
    createdAt: str
    readAt: str | None = None


class Gate(BaseModel):
    id: str
    assignmentId: str
    kind: GateKind
    openedBy: str  # 'system' | 'trigger:<name>' | node id | 'operator'
    owner: str  # who may resolve: node id or 'operator' ('system' for mechanical gates)
    reason: str
    payload: dict[str, Any]
    state: GateState
    resolution: dict[str, Any] | None = None
    resolvedBy: str | None = None
    createdAt: str
    resolvedAt: str | None = None


class MemoryEntry(BaseModel):
    teamId: str
    nodeId: str
    seq: int
    entry: dict[str, Any]
    createdAt: str


class Cadence(BaseModel):
    """A standing schedule (engine.md §4): each due occurrence becomes an ordinary episodic
    intent on ``nodeId`` (None ⇒ the team root), tagged with this cadence's id."""

    id: str
    teamId: str
    nodeId: str | None = None
    name: str
    cron: str  # five UTC fields: minute hour day-of-month month day-of-week
    intentText: str
    enabled: bool
    lastFiredAt: str | None = None
    createdAt: str


class Trigger(BaseModel):
    """An event-driven work source (standing-teams.md §2): polls a connector instance and opens
    one episodic intent per new external event, deduped by the fire ledger — the cursor is an
    optimization, the ledger is the guarantee."""

    id: str
    teamId: str
    name: str
    kind: str  # 'github-issues' (v1's only kind)
    nodeId: str | None = None
    instanceId: str
    config: dict[str, Any] = Field(default_factory=dict)
    intentTemplate: str
    enabled: bool = True
    cursor: dict[str, Any] | None = None
    lastCheckedAt: str | None = None
    lastFiredAt: str | None = None
    lastError: str | None = None
    createdAt: str
    updatedAt: str
