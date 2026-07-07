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


def _assignment_detail(work_store, ledger, assignment) -> dict[str, Any]:
    """The full drill-down for one assignment (brief versions, plan, steps, meter, deliverable)."""
    plan = work_store.get_plan(assignment.id)
    deliverable = (
        work_store.get_deliverable(assignment.deliverableId) if assignment.deliverableId else None
    )
    meter = ledger.get_meter(assignment.meterId)
    return {
        "assignment": assignment.model_dump(),
        "briefs": [b.model_dump() for b in work_store.list_briefs(assignment.id)],
        "plan": plan.model_dump() if plan else None,
        "steps": [s.model_dump() for s in work_store.list_steps(assignment.id)],
        "meter": meter.model_dump() if meter else None,
        "deliverable": deliverable.model_dump() if deliverable else None,
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
