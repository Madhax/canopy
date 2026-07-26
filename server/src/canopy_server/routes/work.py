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
    action: str  # approve | edit-draft | deny (E2a); the judgment actions land in E2b
    assignmentId: str | None = None  # edit-draft: which draft
    brief: str | None = None  # edit-draft: the amended text
    refs: list[str] | None = None  # edit-draft: amended granted refs
    note: str = ""
    allowances: dict[str, int] | None = None  # approve: per-child allowance overrides


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
    try:
        gate = engine.resolve_gate(
            gate_id, action=body.action, resolved_by="operator", payload=payload,
        )
    except WorkError as exc:
        return _error(409, "WORK_STATE", str(exc))
    return gate.model_dump()
