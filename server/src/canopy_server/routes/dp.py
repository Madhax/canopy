"""Data plane API (``/api/dp/*``) — run-token auth only, loopback-bound in v1.

This is the surface agents call. In A1 only the Model Gateway lives here (``llm/complete``); A2
adds ``register``/``heartbeat``, A3 ``a2a/{targetNodeId}``/``inbox/poll``, A4 ``artifacts``. Auth is
the per-agent run token in the ``Authorization: Bearer`` header — an agent can act only as itself
(sandbox.md §5).
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..artifacts import ArtifactTooLarge
from ..deps import (
    get_actuator,
    get_artifact_store,
    get_directory,
    get_engine,
    get_gateway,
    get_ledger,
    get_router,
    get_runtokens,
    get_work_store,
)
from ..engine.engine import WorkError
from ..gateway.base import CompletionRequest, Message, StepKind, ToolSpec
from ..gateway.service import GatewayBudgetExhausted, GatewayError
from ..router import ChannelForbidden

router = APIRouter(prefix="/dp")


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": {"code": "RUN_TOKEN_INVALID", "message": "unknown or missing run token"}},
    )


class CompleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: str = ""
    messages: list[Message] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)
    maxOutputTokens: int = 4096
    temperature: float = 0.7
    providerOptions: dict[str, Any] = Field(default_factory=dict)
    kind: StepKind = "production"
    taskId: str | None = None


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


@router.post("/llm/complete")
async def llm_complete(
    body: CompleteBody,
    authorization: str | None = Header(default=None),
    gateway=Depends(get_gateway),
) -> Any:
    token = _bearer(authorization)
    if not token:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "RUN_TOKEN_MISSING", "message": "run token required"}},
        )
    req = CompletionRequest(
        system=body.system,
        messages=body.messages,
        tools=body.tools,
        maxOutputTokens=body.maxOutputTokens,
        temperature=body.temperature,
        providerOptions=body.providerOptions,
    )
    try:
        result = await gateway.complete(token, req, kind=body.kind, task_id=body.taskId)
    except GatewayBudgetExhausted as exc:
        return JSONResponse(
            status_code=402,
            content={
                "error": {"code": exc.code, "message": exc.message, "meterId": exc.meterId}
            },
        )
    except GatewayError as exc:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
    return result.model_dump()


# --------------------------------------------------------------------------- #
# Boot / liveness surface (A2): charter fetch, register, heartbeat
# --------------------------------------------------------------------------- #
class RegisterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    card: dict[str, Any] = Field(default_factory=dict)


class HeartbeatBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = None
    note: str | None = None


@router.get("/charter")
def get_charter(
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    actuator=Depends(get_actuator),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    charter = actuator.get_charter(rec.actuationId, rec.nodeId)
    if charter is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NO_CHARTER", "message": "no charter for this node yet"}},
        )
    return charter


@router.post("/register")
def register(
    body: RegisterBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    directory=Depends(get_directory),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    directory.register(rec.actuationId, rec.nodeId, body.endpoint, body.card)
    return {"ok": True}


@router.post("/heartbeat")
def heartbeat(
    body: HeartbeatBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    directory=Depends(get_directory),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    directory.heartbeat(rec.actuationId, rec.nodeId, body.status)  # type: ignore[arg-type]
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Mediated A2A (A3): the ONLY way any agent reaches any other. Topology-checked.
# --------------------------------------------------------------------------- #
class A2ASendBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any] = Field(default_factory=dict)
    taskRef: str | None = None
    idempotencyKey: str | None = None


@router.post("/a2a/{target_node_id}")
def a2a_send(
    target_node_id: str,
    body: A2ASendBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    message_router=Depends(get_router),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    try:
        sent = message_router.send(
            rec.actuationId, rec.nodeId, target_node_id, body.payload,
            task_ref=body.taskRef, idempotency_key=body.idempotencyKey,
        )
    except ChannelForbidden as exc:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": exc.code, "message": str(exc),
                               "from": exc.fromNode, "to": exc.toNode}},
        )
    return sent.model_dump()


# --------------------------------------------------------------------------- #
# Execution Engine data plane (E1): the caller's assignment, progress reports,
# plan declaration, deliverable submission, and Artifact Store put/fetch. Every
# call is scoped to the caller's own assignment (engine.md §5) — an agent acts
# only as itself and only on work addressed to it.
# --------------------------------------------------------------------------- #
class EventBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    kind: str  # intake-complete | step | stage-update | delivering
    inputTokens: int = 0
    outputTokens: int = 0
    durationMs: int = 0
    stepKind: StepKind = "production"
    stageIdx: int | None = None
    deltaKind: str = "none"
    deltaRef: str | None = None
    stepId: str | None = None
    sessionSpanId: str | None = None
    stageState: str | None = None


class PlanStageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    completion: str = ""
    sizing: str = "medium"
    envelopeTokens: int | None = None


class PlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    stages: list[PlanStageIn] = Field(default_factory=list)


class FinishBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    kind: str | None = None
    refs: list[str] = Field(default_factory=list)
    summary: str = ""
    attestation: dict[str, Any] | None = None


class ArtifactPutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    name: str
    type: str
    contentBase64: str
    filename: str | None = None


def _work_conflict(exc: WorkError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": {"code": "WORK_STATE",
                                                            "message": str(exc)}})


def _owned(work_store, rec, assignment_id: str):
    """(assignment, None) if the caller owns it, else (None, error-response)."""
    a = work_store.get_assignment(assignment_id)
    if a is None:
        return None, JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND",
                                  "message": f"no assignment {assignment_id}"}})
    if a.actuationId != rec.actuationId or a.nodeId != rec.nodeId:
        return None, JSONResponse(status_code=403, content={"error": {"code": "NOT_YOUR_ASSIGNMENT",
                                  "message": "assignment belongs to another node"}})
    return a, None


@router.get("/assignment/current")
def assignment_current(
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    ledger=Depends(get_ledger),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    a = work_store.current_assignment(rec.actuationId, rec.nodeId)
    if a is None:
        return JSONResponse(content=None)  # nothing to do — the runtime idles
    brief = work_store.get_brief(a.id)
    meter = ledger.get_meter(a.meterId)
    return {
        "assignment": a.model_dump(),
        "brief": brief.model_dump() if brief else None,
        "contract": {"kind": a.contractKind, "type": a.contractType},
        "memory": [m.entry for m in work_store.get_memory(rec.orgId, rec.nodeId)],
        "meter": meter.model_dump() if meter else None,
    }


@router.get("/meter")
def current_meter(
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    ledger=Depends(get_ledger),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    a = work_store.current_assignment(rec.actuationId, rec.nodeId)
    meter = ledger.get_meter(a.meterId) if a else None
    return JSONResponse(content=meter.model_dump() if meter else None)


@router.post("/plan")
def declare_plan(
    body: PlanBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        plan = engine.declare_plan(body.assignmentId, [s.model_dump() for s in body.stages])
    except WorkError as exc:
        return _work_conflict(exc)
    return plan.model_dump()


@router.post("/assignment/events")
def assignment_events(
    body: EventBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        if body.kind == "intake-complete":
            engine.mark_intake_complete(body.assignmentId)
        elif body.kind == "step":
            engine.record_step(
                body.assignmentId, input_tokens=body.inputTokens, output_tokens=body.outputTokens,
                duration_ms=body.durationMs, kind=body.stepKind, stage_idx=body.stageIdx,
                delta_kind=body.deltaKind, delta_ref=body.deltaRef, step_id=body.stepId,
                session_span_id=body.sessionSpanId,
            )
        elif body.kind == "stage-update":
            if body.stageIdx is None or body.stageState is None:
                return _work_conflict(WorkError("stage-update needs stageIdx and stageState"))
            engine.update_stage(body.assignmentId, body.stageIdx, body.stageState)
        elif body.kind == "delivering":
            pass  # advisory; the deliverable is submitted via /dp/finish
        else:
            return _work_conflict(WorkError(f"unknown event kind {body.kind!r}"))
    except WorkError as exc:
        return _work_conflict(exc)
    return work_store.get_assignment(body.assignmentId).model_dump()


@router.post("/finish")
def finish(
    body: FinishBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        deliverable = engine.finish(
            body.assignmentId, artifact_refs=body.refs, summary=body.summary, kind=body.kind,
            attestation=body.attestation,
        )
    except WorkError as exc:
        return _work_conflict(exc)
    return deliverable.model_dump()


@router.post("/artifacts")
def put_artifact(
    body: ArtifactPutBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        content = base64.b64decode(body.contentBase64)
    except (ValueError, binascii.Error):
        return JSONResponse(status_code=422, content={"error": {"code": "BAD_CONTENT",
                            "message": "contentBase64 is not valid base64"}})
    try:
        meta = engine.put_artifact(body.assignmentId, body.name, body.type, content,
                                   filename=body.filename)
    except ArtifactTooLarge as exc:
        return JSONResponse(status_code=413, content={"error": {"code": "ARTIFACT_TOO_LARGE",
                            "message": str(exc)}})
    return meta.model_dump()


@router.get("/artifacts")
def fetch_artifact(
    ref: str,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    artifacts=Depends(get_artifact_store),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    meta = artifacts.resolve(ref)
    if meta is None or meta.orgId != rec.orgId:
        return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND",
                            "message": f"no artifact {ref}"}})
    content = artifacts.read(ref)
    return {"meta": meta.model_dump(),
            "contentBase64": base64.b64encode(content).decode() if content else None}
