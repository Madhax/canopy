"""Work-layer boundary shapes and state enums (work-model.md).

camelCase Pydantic at the boundary, snake_case in SQLite (the store maps between them). These are
the domain's objects made concrete: Intent → Assignment → Brief / Plan / Step → Deliverable, plus
durable per-node Memory. State machines live here as ``Literal`` sets so both the store and the
engine share one source of truth for "what states exist".
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# State enums (the domain's, verbatim — work-model.md §1, §2.1, §4, §5).
# --------------------------------------------------------------------------- #
IntentKind = Literal["episodic", "standing"]
IntentState = Literal["open", "completed", "failed", "cancelled"]

AssignmentState = Literal[
    "created", "briefed", "intake", "planning", "executing", "delivering",
    "accepted", "rejected", "closed", "gated", "paused", "cancelled", "failed",
]
#: Assignment is live work — a runtime may be driving it or it may be waiting on a gate/hold.
ASSIGNMENT_ACTIVE_STATES: frozenset[str] = frozenset({
    "created", "briefed", "intake", "planning", "executing", "delivering", "rejected",
    "gated", "paused",
})
#: Nothing more happens; the row is history.
ASSIGNMENT_TERMINAL_STATES: frozenset[str] = frozenset({
    "accepted", "closed", "cancelled", "failed",
})

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
    orgId: str
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


class Assignment(BaseModel):
    id: str
    orgId: str
    actuationId: str
    intentId: str
    parentId: str | None
    nodeId: str
    issuedBy: str
    state: AssignmentState
    briefVersion: int
    contractKind: ContractKind
    contractType: str
    meterId: str
    priority: int
    deliverableId: str | None = None
    reassignedFrom: str | None = None
    sessionRef: str | None = None
    createdAt: str
    updatedAt: str
    closedAt: str | None = None


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


class MemoryEntry(BaseModel):
    orgId: str
    nodeId: str
    seq: int
    entry: dict[str, Any]
    createdAt: str
