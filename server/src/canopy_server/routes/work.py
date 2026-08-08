"""Operator work API — intents and assignments (engine.md §6, extends control-plane.md §9).

The operator's window into work truth: submit an intent (which creates a work_intent + its root
Assignment via the engine), list/inspect intents, and drill into any assignment's brief versions,
plan, steps, meter, and deliverable. Unauthenticated in v1 like the rest of the operator API
(loopback-bound); the data-plane surface (`dp.py`) is the run-token-gated one.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..deps import (
    get_activity,
    get_actuator,
    get_artifact_store,
    get_engine,
    get_ledger,
    get_store,
    get_work_store,
    now_iso,
)
from ..engine.cadence import CronError, next_fire, parse_cron, validate_cron
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
        deliverable = work_store.get_deliverable(a.deliverableId) if a.deliverableId else None
        return {
            "assignment": a.model_dump(),
            "brief": (b := work_store.get_brief(a.id)) and b.model_dump(),
            "briefVersions": a.briefVersion,
            "plan": plan.model_dump() if plan else None,
            "gates": [g.model_dump()
                      for g in work_store.list_gates(assignment_id=a.id, state="open")],
            "meter": meter.model_dump() if meter else None,
            "deliverable": deliverable.model_dump() if deliverable else None,
            "notes": [n.model_dump() for n in notes if n.assignmentId == a.id],
            "children": [node_view(c) for c in by_parent.get(a.id, [])],
        }

    roots = by_parent.get(None, [])
    return {
        "intent": intent.model_dump(),
        "tree": [node_view(r) for r in roots],
        "intentNotes": [n.model_dump() for n in notes if n.assignmentId is None],
    }


# The operator's artifact preview (the deliverable viewer): meta + utf-8 content for text
# artifacts ≤ 256 KB, mirroring the inspector's workspace preview conventions. The data-plane
# GET (dp.py) stays the grant-checked *agent* path; this one is org-scoped operator API like
# everything else here — you can't accept what you can't see.
_ARTIFACT_PREVIEW_LIMIT = 256 * 1024


@router.get("/organizations/{org_id}/artifacts")
def read_artifact(org_id: str, ref: str, artifacts=Depends(get_artifact_store)) -> Any:
    meta = artifacts.resolve(ref)
    if meta is None or meta.orgId != org_id:
        return _error(404, "NOT_FOUND", f"No artifact {ref!r} in this organization")
    out: dict[str, Any] = {"meta": meta.model_dump(), "content": None, "reason": None}
    if meta.size > _ARTIFACT_PREVIEW_LIMIT:
        out["reason"] = "too-large"
        return out
    raw = artifacts.read(ref)
    if raw is None:
        out["reason"] = "missing-blob"
        return out
    if b"\x00" in raw[:8192]:
        out["reason"] = "binary"
        return out
    out["content"] = raw.decode("utf-8", errors="replace")
    return out


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


# --------------------------------------------------------------------------- #
# Cadences (E7, engine.md §4): CRUD over work_cadence. The 30 s scheduler loop in main.py does
# the firing; these routes only manage the schedule rows — and compute the next fire time for
# the management list (operator-experience.md §4).
# --------------------------------------------------------------------------- #
class CadenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    cron: str  # five UTC fields: minute hour day-of-month month day-of-week
    intentText: str
    nodeId: str | None = None  # None ⇒ the org root at fire time
    enabled: bool = True


class CadenceUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    cron: str | None = None
    intentText: str | None = None
    nodeId: str | None = None  # None ⇒ unchanged (retarget-to-root = recreate)
    enabled: bool | None = None


def _cadence_view(c) -> dict[str, Any]:
    """The row + its computed ``nextFireAt`` (from now — a disabled cadence has none)."""
    out = c.model_dump()
    nxt = None
    if c.enabled:
        try:
            due = next_fire(parse_cron(c.cron), datetime.fromisoformat(now_iso()))
            nxt = due.isoformat().replace("+00:00", "Z") if due else None
        except CronError:
            nxt = None
    out["nextFireAt"] = nxt
    return out


def _check_cadence_node(store, org_id: str, node_id: str | None) -> JSONResponse | None:
    if node_id is None:
        return None
    org = store.read(org_id)
    if not any(a.id == node_id for a in org.agents):
        return _error(422, "BAD_NODE", f"node {node_id!r} not found in org {org_id!r}")
    return None


@router.get("/organizations/{org_id}/cadences")
def list_cadences(org_id: str, work_store=Depends(get_work_store)) -> Any:
    return {"cadences": [_cadence_view(c) for c in work_store.list_cadences(org_id)]}


@router.post("/organizations/{org_id}/cadences", status_code=201)
def create_cadence(
    org_id: str, body: CadenceBody, store=Depends(get_store),
    work_store=Depends(get_work_store), activity=Depends(get_activity),
) -> Any:
    if not store.exists(org_id):
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    if not body.name.strip() or not body.intentText.strip():
        return _error(422, "BAD_CADENCE", "name and intentText are required")
    try:
        validate_cron(body.cron)
    except CronError as exc:
        return _error(422, "BAD_CRON", str(exc))
    if (err := _check_cadence_node(store, org_id, body.nodeId)) is not None:
        return err
    cadence = work_store.create_cadence(
        org_id, body.name.strip(), body.cron, body.intentText.strip(),
        node_id=body.nodeId, enabled=body.enabled,
    )
    activity.log("operator", "cadence.created", org_id=org_id, subject_ids=[cadence.id],
                 payload={"cron": cadence.cron})
    return _cadence_view(cadence)


@router.put("/organizations/{org_id}/cadences/{cadence_id}")
def update_cadence(
    org_id: str, cadence_id: str, body: CadenceUpdateBody, store=Depends(get_store),
    work_store=Depends(get_work_store), activity=Depends(get_activity),
) -> Any:
    existing = work_store.get_cadence(cadence_id)
    if existing is None or existing.orgId != org_id:
        return _error(404, "NOT_FOUND", f"No cadence {cadence_id!r}")
    if body.cron is not None:
        try:
            validate_cron(body.cron)
        except CronError as exc:
            return _error(422, "BAD_CRON", str(exc))
    if (err := _check_cadence_node(store, org_id, body.nodeId)) is not None:
        return err
    cadence = work_store.update_cadence(
        cadence_id, name=body.name, cron=body.cron, intent_text=body.intentText,
        node_id=body.nodeId, enabled=body.enabled,
    )
    activity.log("operator", "cadence.updated", org_id=org_id, subject_ids=[cadence_id],
                 payload={"enabled": cadence.enabled})
    return _cadence_view(cadence)


@router.delete("/organizations/{org_id}/cadences/{cadence_id}", status_code=204)
def delete_cadence(
    org_id: str, cadence_id: str, work_store=Depends(get_work_store),
    activity=Depends(get_activity),
):
    existing = work_store.get_cadence(cadence_id)
    if existing is None or existing.orgId != org_id:
        return _error(404, "NOT_FOUND", f"No cadence {cadence_id!r}")
    work_store.delete_cadence(cadence_id)
    activity.log("operator", "cadence.deleted", org_id=org_id, subject_ids=[cadence_id])
    return JSONResponse(status_code=204, content=None)


# --------------------------------------------------------------------------- #
# Triggers (standing-orgs.md §4): CRUD over work_trigger + the check-now / dry-run verbs.
# The 60 s poll loop in main.py does the firing; these routes manage the source rows.
# --------------------------------------------------------------------------- #
class TriggerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    kind: str = "github-issues"
    instanceId: str
    intentTemplate: str
    nodeId: str | None = None  # None ⇒ the org root at fire time
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class TriggerUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    instanceId: str | None = None
    intentTemplate: str | None = None
    nodeId: str | None = None  # None ⇒ unchanged (retarget-to-root = recreate)
    config: dict[str, Any] | None = None
    enabled: bool | None = None


def _check_trigger_template(template: str) -> JSONResponse | None:
    import re

    from ..github_client import TEMPLATE_VARS

    for var in re.findall(r"\{\{(\w+)\}\}", template):
        if var not in TEMPLATE_VARS:
            return _error(422, "BAD_TEMPLATE",
                          f"unknown placeholder {{{{{var}}}}} — "
                          f"vocabulary: {', '.join(TEMPLATE_VARS)}")
    return None


def _check_trigger_source(org_id: str, instance_id: str) -> JSONResponse | None:
    """The instance must exist, be enabled, and serve issues.read (standing-orgs.md §4)."""
    from ..catalog import get_catalog
    from ..deps import get_connector_store

    connectors = get_connector_store()
    inst = connectors.get(instance_id)
    if inst is None or inst.organizationId != org_id:
        return _error(422, "BAD_TRIGGER_SOURCE", f"no connector instance {instance_id!r}")
    if not inst.enabled:
        return _error(422, "BAD_TRIGGER_SOURCE", f"instance {inst.name!r} is disabled")
    binding = connectors.resolve(get_catalog(), org_id, None, "issues.read")
    if binding is None or binding.instance.id != instance_id:
        # Resolve directly against this instance: it must carry an enabled issues-read grant.
        pack = next((p for p in get_catalog().connectorPacks if p.key == inst.packKey), None)
        serves = pack is not None and any(
            g.key in inst.enabledGrants and ("issues.read" in g.provides)
            for g in pack.grants
        )
        if not serves:
            return _error(422, "BAD_TRIGGER_SOURCE",
                          f"instance {inst.name!r} does not serve issues.read — "
                          "enable the issue-read capability on it first")
    return None


@router.get("/organizations/{org_id}/triggers")
def list_triggers(org_id: str, work_store=Depends(get_work_store)) -> Any:
    return {"triggers": [t.model_dump() for t in work_store.list_triggers(org_id)]}


@router.post("/organizations/{org_id}/triggers", status_code=201)
def create_trigger(
    org_id: str, body: TriggerBody, store=Depends(get_store),
    work_store=Depends(get_work_store), activity=Depends(get_activity),
) -> Any:
    if not store.exists(org_id):
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    if not body.name.strip() or not body.intentTemplate.strip():
        return _error(422, "BAD_TRIGGER", "name and intentTemplate are required")
    if body.kind != "github-issues":
        return _error(422, "BAD_TRIGGER", f"unknown trigger kind {body.kind!r}")
    if (err := _check_trigger_template(body.intentTemplate)) is not None:
        return err
    if (err := _check_cadence_node(store, org_id, body.nodeId)) is not None:
        return err
    if (err := _check_trigger_source(org_id, body.instanceId)) is not None:
        return err
    config = dict(body.config)
    # A new trigger never replays history unless asked (standing-orgs-ux.md §2.1).
    config.setdefault("createdAfter", now_iso())
    trigger = work_store.create_trigger(
        org_id, body.name.strip(), body.kind, body.instanceId,
        body.intentTemplate.strip(), node_id=body.nodeId, config=config,
        enabled=body.enabled,
    )
    activity.log("operator", "trigger.created", org_id=org_id, subject_ids=[trigger.id],
                 payload={"kind": trigger.kind, "instanceId": trigger.instanceId})
    return trigger.model_dump()


@router.put("/organizations/{org_id}/triggers/{trigger_id}")
def update_trigger(
    org_id: str, trigger_id: str, body: TriggerUpdateBody, store=Depends(get_store),
    work_store=Depends(get_work_store), activity=Depends(get_activity),
) -> Any:
    existing = work_store.get_trigger(trigger_id)
    if existing is None or existing.orgId != org_id:
        return _error(404, "NOT_FOUND", f"No trigger {trigger_id!r}")
    if body.intentTemplate is not None:
        if (err := _check_trigger_template(body.intentTemplate)) is not None:
            return err
    if (err := _check_cadence_node(store, org_id, body.nodeId)) is not None:
        return err
    if body.instanceId is not None:
        if (err := _check_trigger_source(org_id, body.instanceId)) is not None:
            return err
    changes: dict[str, Any] = {}
    for field, key in (("name", "name"), ("instanceId", "instanceId"),
                       ("intentTemplate", "intentTemplate"), ("nodeId", "nodeId"),
                       ("config", "config"), ("enabled", "enabled")):
        val = getattr(body, field)
        if val is not None:
            changes[key] = val
    trigger = work_store.update_trigger(trigger_id, changes)
    activity.log("operator", "trigger.updated", org_id=org_id, subject_ids=[trigger_id],
                 payload={"enabled": trigger.enabled})
    return trigger.model_dump()


@router.delete("/organizations/{org_id}/triggers/{trigger_id}", status_code=204)
def delete_trigger(
    org_id: str, trigger_id: str, work_store=Depends(get_work_store),
    activity=Depends(get_activity),
):
    existing = work_store.get_trigger(trigger_id)
    if existing is None or existing.orgId != org_id:
        return _error(404, "NOT_FOUND", f"No trigger {trigger_id!r}")
    work_store.delete_trigger(trigger_id)
    activity.log("operator", "trigger.deleted", org_id=org_id, subject_ids=[trigger_id])
    return JSONResponse(status_code=204, content=None)


@router.post("/organizations/{org_id}/triggers/{trigger_id}/check")
def check_trigger(
    org_id: str, trigger_id: str, work_store=Depends(get_work_store),
) -> Any:
    """One synchronous poll for this trigger — the operator's *check now* button."""
    from ..deps import get_trigger_scheduler

    existing = work_store.get_trigger(trigger_id)
    if existing is None or existing.orgId != org_id:
        return _error(404, "NOT_FOUND", f"No trigger {trigger_id!r}")
    return get_trigger_scheduler().check_now(trigger_id)


@router.post("/organizations/{org_id}/triggers/{trigger_id}/dry-run")
def dry_run_trigger(
    org_id: str, trigger_id: str, work_store=Depends(get_work_store),
) -> Any:
    """The poll without the firing: what WOULD fire, with the first intent rendered."""
    from ..deps import get_trigger_scheduler
    from ..github_client import GitHubError

    existing = work_store.get_trigger(trigger_id)
    if existing is None or existing.orgId != org_id:
        return _error(404, "NOT_FOUND", f"No trigger {trigger_id!r}")
    try:
        return get_trigger_scheduler().dry_run(trigger_id)
    except (GitHubError, LookupError) as exc:
        return _error(502, "TRIGGER_SOURCE_ERROR", str(exc))


# --------------------------------------------------------------------------- #
# The SSE channel (engine.md §6): one live stream per org. Activity transitions ride through
# individually (id = seq, so Last-Event-ID resume works); step/plan/note/notification changes
# arrive as coalesced per-family events — at most one per tick, which is the server-side step
# throttle. The tail is DB-driven: anything that lands in the store surfaces here without
# engine hooks, and a dropped stream loses nothing (the UI falls back to polling and the
# cursor resumes).
# --------------------------------------------------------------------------- #
EVENTS_TICK_SECONDS = 1.0
_KEEPALIVE_TICKS = 15
_COALESCED_FAMILIES = ("steps", "plan", "notes", "notifications")


def _sse(event: str, data: dict, *, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n"


async def _org_event_stream(
    request: Request, org_id: str, after: int | None, activity, work_store,
):
    last_seq = activity.max_seq(org_id) if after is None else after
    marks = work_store.change_watermark(org_id)
    yield _sse("hello", {"seq": last_seq})
    quiet_ticks = 0
    while not await request.is_disconnected():
        wrote = False
        for row in activity.list(org_id, after_seq=last_seq, limit=200):
            last_seq = row["seq"]
            yield _sse(
                "activity",
                {"seq": row["seq"], "ts": row["ts"], "kind": row["kind"],
                 "subjectIds": row["subjectIds"]},
                event_id=row["seq"],
            )
            wrote = True
        fresh = work_store.change_watermark(org_id)
        for family in _COALESCED_FAMILIES:
            if fresh[family] != marks[family]:
                yield _sse(family, {})
                wrote = True
        marks = fresh
        quiet_ticks = 0 if wrote else quiet_ticks + 1
        if quiet_ticks >= _KEEPALIVE_TICKS:
            yield ": keepalive\n\n"
            quiet_ticks = 0
        await asyncio.sleep(EVENTS_TICK_SECONDS)


@router.get("/organizations/{org_id}/events")
async def org_events(
    org_id: str,
    request: Request,
    after: int | None = None,
    store=Depends(get_store),
    work_store=Depends(get_work_store),
    activity=Depends(get_activity),
) -> Any:
    if not store.exists(org_id):
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    last_event_id = request.headers.get("last-event-id")
    if after is None and last_event_id and last_event_id.isdigit():
        after = int(last_event_id)
    return StreamingResponse(
        _org_event_stream(request, org_id, after, activity, work_store),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
