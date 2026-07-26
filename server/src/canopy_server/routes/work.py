"""Operator work API — intents and assignments (engine.md §6, extends control-plane.md §9).

The operator's window into work truth: submit an intent (which creates a work_intent + its root
Assignment via the engine), list/inspect intents, and drill into any assignment's brief versions,
plan, steps, meter, and deliverable. Unauthenticated in v1 like the rest of the operator API
(loopback-bound); the data-plane surface (`dp.py`) is the run-token-gated one.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ..deps import get_actuator, get_engine, get_ledger, get_store, get_work_store
from ..engine.engine import WorkError

router = APIRouter()


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


class IntentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    targetNodeId: str | None = None
    kind: str = "episodic"
    allowanceOverride: int | None = None


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = ""
    revisedBrief: str | None = None  # reject only — triggers the rework-funding rule


class GateResolveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str  # approve | edit-draft | deny | resume | revise-brief | answer |
    #              top-up | reassign | cancel (work-model.md §3 resolution table)
    assignmentId: str | None = None  # edit-draft: which draft
    brief: str | None = None  # edit-draft / revise-brief: the (amended) text
    refs: list[str] | None = None  # granted refs riding the resolution
    note: str = ""
    allowances: dict[str, int] | None = None  # approve: per-child allowance overrides
    answer: str | None = None  # escalation answer
    amount: int | None = None  # top-up
    toNodeId: str | None = None  # reassign target


def _assignment_detail(work_store, ledger, assignment) -> dict[str, Any]:
    """The full drill-down for one assignment (brief versions, plan, steps, meter, deliverable)."""
    plan = work_store.get_plan(assignment.id)
    deliverable = (
        work_store.get_deliverable(assignment.deliverableId) if assignment.deliverableId else None
    )
    meter = ledger.get_meter(assignment.meterId) if assignment.meterId else None
    return {
        "assignment": assignment.model_dump(),
        "briefs": [b.model_dump() for b in work_store.list_briefs(assignment.id)],
        "plan": plan.model_dump() if plan else None,
        "steps": [s.model_dump() for s in work_store.list_steps(assignment.id)],
        "meter": meter.model_dump() if meter else None,
        "deliverable": deliverable.model_dump() if deliverable else None,
        "gates": [g.model_dump() for g in work_store.list_gates(assignment_id=assignment.id)],
    }


@router.post("/organizations/{org_id}/intents", status_code=201)
def submit_intent(
    org_id: str,
    body: IntentBody,
    store=Depends(get_store),
    actuator=Depends(get_actuator),
    engine=Depends(get_engine),
) -> Any:
    if not store.exists(org_id):
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    current = actuator.get_current(org_id)
    if current is None or current.state not in ("live", "degraded"):
        return _error(409, "NOT_ACTUATED", "Actuate the organization before submitting intents.")
    try:
        res = engine.submit_intent(
            org_id, current.id, body.text, target_node=body.targetNodeId, kind=body.kind,
            allowance_override=body.allowanceOverride,
        )
    except WorkError as exc:
        return _error(422, "BAD_INTENT", str(exc))
    return {"intent": res.intent.model_dump(), "assignment": res.assignment.model_dump()}


@router.get("/organizations/{org_id}/intents")
def list_intents(org_id: str, work_store=Depends(get_work_store)) -> Any:
    return {"intents": [i.model_dump() for i in work_store.list_intents(org_id)]}


@router.get("/intents/{intent_id}")
def intent_detail(
    intent_id: str, work_store=Depends(get_work_store), ledger=Depends(get_ledger)
) -> Any:
    intent = work_store.get_intent(intent_id)
    if intent is None:
        return _error(404, "NOT_FOUND", f"No intent {intent_id!r}")
    assignments = work_store.list_assignments(intent_id=intent_id)
    return {
        "intent": intent.model_dump(),
        "assignments": [_assignment_detail(work_store, ledger, a) for a in assignments],
    }


@router.get("/organizations/{org_id}/assignments")
def list_assignments(
    org_id: str,
    node: str | None = None,
    state: str | None = None,
    work_store=Depends(get_work_store),
) -> Any:
    rows = work_store.list_assignments(org_id=org_id, node_id=node, state=state)
    return {"assignments": [a.model_dump() for a in rows]}


@router.get("/assignments/{assignment_id}")
def assignment_detail(
    assignment_id: str, work_store=Depends(get_work_store), ledger=Depends(get_ledger)
) -> Any:
    a = work_store.get_assignment(assignment_id)
    if a is None:
        return _error(404, "NOT_FOUND", f"No assignment {assignment_id!r}")
    return _assignment_detail(work_store, ledger, a)


# --------------------------------------------------------------------------- #
# Acceptance + gates (E2): the operator side of the review and resolution surface.
# Manager-side accept/reject travels the data plane (dp.py) with run-token auth.
# --------------------------------------------------------------------------- #
@router.post("/assignments/{assignment_id}/accept")
def operator_accept(
    assignment_id: str, body: ReviewBody, engine=Depends(get_engine),
    work_store=Depends(get_work_store),
) -> Any:
    if work_store.get_assignment(assignment_id) is None:
        return _error(404, "NOT_FOUND", f"No assignment {assignment_id!r}")
    try:
        a = engine.accept(assignment_id, note=body.note or None)
    except WorkError as exc:
        return _error(409, "WORK_STATE", str(exc))
    return a.model_dump()


@router.post("/assignments/{assignment_id}/reject")
def operator_reject(
    assignment_id: str, body: ReviewBody, engine=Depends(get_engine),
    work_store=Depends(get_work_store),
) -> Any:
    if work_store.get_assignment(assignment_id) is None:
        return _error(404, "NOT_FOUND", f"No assignment {assignment_id!r}")
    try:
        a = engine.reject(assignment_id, body.note, revised_brief=body.revisedBrief)
    except WorkError as exc:
        return _error(409, "WORK_STATE", str(exc))
    return a.model_dump()


class InterveneBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str


class PriorityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: int


class NoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    assignmentId: str | None = None  # None ⇒ a note on the intent itself
    stageIdx: int | None = None


class NotificationsReadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] | None = None  # None ⇒ mark all unread read


@router.post("/assignments/{assignment_id}/intervene")
def intervene(
    assignment_id: str, body: InterveneBody, engine=Depends(get_engine),
    work_store=Depends(get_work_store),
) -> Any:
    """X1: the operator's judgment suspends the assignment on an InterventionGate."""
    if work_store.get_assignment(assignment_id) is None:
        return _error(404, "NOT_FOUND", f"No assignment {assignment_id!r}")
    try:
        gate = engine.intervene(assignment_id, body.note, by="operator")
    except WorkError as exc:
        return _error(409, "WORK_STATE", str(exc))
    return gate.model_dump()


@router.post("/assignments/{assignment_id}/priority")
def set_priority(
    assignment_id: str, body: PriorityBody, engine=Depends(get_engine),
    work_store=Depends(get_work_store),
) -> Any:
    if work_store.get_assignment(assignment_id) is None:
        return _error(404, "NOT_FOUND", f"No assignment {assignment_id!r}")
    return engine.set_priority(assignment_id, body.priority).model_dump()


@router.post("/intents/{intent_id}/notes", status_code=201)
def leave_note(
    intent_id: str, body: NoteBody, work_store=Depends(get_work_store),
) -> Any:
    """Amendment D-5: an anchored, non-blocking note — injected at the target's next turn
    boundary; opens no gate, revises no brief."""
    intent = work_store.get_intent(intent_id)
    if intent is None:
        return _error(404, "NOT_FOUND", f"No intent {intent_id!r}")
    if body.assignmentId is not None:
        a = work_store.get_assignment(body.assignmentId)
        if a is None or a.intentId != intent_id:
            return _error(422, "BAD_ANCHOR", "assignmentId is not part of this intent")
    note = work_store.create_note(
        intent.orgId, intent_id, body.text, assignment_id=body.assignmentId,
        stage_idx=body.stageIdx, author="operator",
    )
    return note.model_dump()


@router.get("/intents/{intent_id}/plan")
def intent_plan(
    intent_id: str, work_store=Depends(get_work_store), ledger=Depends(get_ledger),
) -> Any:
    """The living-plan aggregate (amendment D-4): the whole engagement as one payload —
    assignment tree with per-node plans (stages, cursors, timestamps), brief versions, open
    gates, meters, and anchored notes. Read + act; this view stores nothing."""
    intent = work_store.get_intent(intent_id)
    if intent is None:
        return _error(404, "NOT_FOUND", f"No intent {intent_id!r}")
    assignments = work_store.list_assignments(intent_id=intent_id)
    notes = work_store.list_notes(intent_id)
    by_parent: dict[str | None, list] = {}
    for a in assignments:
        by_parent.setdefault(a.parentId, []).append(a)

    def node_view(a) -> dict[str, Any]:
        plan = work_store.get_plan(a.id)
        meter = ledger.get_meter(a.meterId) if a.meterId else None
        return {
            "assignment": a.model_dump(),
            "brief": (b := work_store.get_brief(a.id)) and b.model_dump(),
            "briefVersions": a.briefVersion,
            "plan": plan.model_dump() if plan else None,
            "gates": [g.model_dump()
                      for g in work_store.list_gates(assignment_id=a.id, state="open")],
            "meter": meter.model_dump() if meter else None,
            "notes": [n.model_dump() for n in notes if n.assignmentId == a.id],
            "children": [node_view(c) for c in by_parent.get(a.id, [])],
        }

    roots = by_parent.get(None, [])
    return {
        "intent": intent.model_dump(),
        "tree": [node_view(r) for r in roots],
        "intentNotes": [n.model_dump() for n in notes if n.assignmentId is None],
    }


@router.get("/organizations/{org_id}/notifications")
def list_notifications(
    org_id: str, since: str | None = None, unread: bool = False,
    work_store=Depends(get_work_store),
) -> Any:
    rows = work_store.list_notifications(org_id, since=since, unread_only=unread)
    return {"notifications": [n.model_dump() for n in rows]}


@router.post("/organizations/{org_id}/notifications/read")
def mark_notifications_read(
    org_id: str, body: NotificationsReadBody, work_store=Depends(get_work_store),
) -> Any:
    return {"marked": work_store.mark_notifications_read(org_id, body.ids)}


@router.get("/organizations/{org_id}/gates")
def list_gates(
    org_id: str, state: str | None = None, owner: str | None = None,
    work_store=Depends(get_work_store),
) -> Any:
    rows = work_store.list_gates(org_id=org_id, state=state, owner=owner)
    return {"gates": [g.model_dump() for g in rows]}


@router.post("/gates/{gate_id}/resolve")
def resolve_gate(
    gate_id: str, body: GateResolveBody, engine=Depends(get_engine),
    work_store=Depends(get_work_store),
) -> Any:
    if work_store.get_gate(gate_id) is None:
        return _error(404, "NOT_FOUND", f"No gate {gate_id!r}")
    payload: dict[str, Any] = {"note": body.note}
    if body.assignmentId is not None:
        payload["assignmentId"] = body.assignmentId
    if body.brief is not None:
        payload["brief"] = body.brief
    if body.refs is not None:
        payload["refs"] = body.refs
    if body.allowances is not None:
        payload["allowances"] = body.allowances
    if body.answer is not None:
        payload["answer"] = body.answer
    if body.amount is not None:
        payload["amount"] = body.amount
    if body.toNodeId is not None:
        payload["toNodeId"] = body.toNodeId
    try:
        gate = engine.resolve_gate(
            gate_id, action=body.action, resolved_by="operator", payload=payload,
        )
    except WorkError as exc:
        return _error(409, "WORK_STATE", str(exc))
    return gate.model_dump()
