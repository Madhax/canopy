"""Data plane API (``/api/dp/*``) — run-token auth only, loopback-bound in v1.

This is the surface agents call. In A1 only the Model Gateway lives here (``llm/complete``); A2
adds ``register``/``heartbeat``, A3 ``a2a/{targetNodeId}``/``inbox/poll``, A4 ``artifacts``. Auth is
the per-agent run token in the ``Authorization: Bearer`` header — an agent can act only as itself
(sandbox.md §5).
"""

from __future__ import annotations

import base64
import binascii
import json
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
    get_repos,
    get_router,
    get_runtokens,
    get_work_store,
)
from ..engine.engine import WorkError
from ..gateway.base import CompletionRequest, Message, StepKind, ToolSpec
from ..gateway.service import GatewayBudgetExhausted, GatewayError
from ..repos import RepoError
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
    kind: str  # intake-complete | step | stage-update | awaiting-reports | delivering
    #          # | session-health (F14)
    inputTokens: int = 0
    outputTokens: int = 0
    cacheReadTokens: int = 0
    cacheCreationTokens: int = 0
    durationMs: int = 0
    stepKind: StepKind = "production"
    stageIdx: int | None = None
    deltaKind: str = "none"
    deltaRef: str | None = None
    stepId: str | None = None
    sessionSpanId: str | None = None
    stageState: str | None = None
    sessionRef: str | None = None  # 'session-ref' events: the CLI resume handle
    transcriptPath: str | None = None  # 'session-ref' events (F16): the transcript pointer
    settle: bool = False  # session steps: also land the SpendEvent (cli-runtime.md §5)
    model: str = "claude-cli"
    health: str | None = None  # 'session-health' events (F14): running | erroring
    healthDetail: str | None = None


class DependsOnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    resolveOn: str | None = None  # default: the chart's edge policy (work-model.md §3)


class DelegateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str  # the CALLER's assignment (the delegation happens inside it)
    reportNodeId: str
    brief: str
    refs: list[str] = Field(default_factory=list)
    contractKind: str | None = None
    contractType: str | None = None
    dependsOn: list[DependsOnIn] = Field(default_factory=list)


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str  # the REPORT's assignment under review
    note: str = ""
    revisedBrief: str | None = None  # reject only — triggers the rework-funding rule


class GateOpenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    kind: str  # clarification | escalation
    question: str
    refs: list[str] = Field(default_factory=list)


class PriorityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str  # the REPORT's assignment (R3: manager-set)
    priority: int


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
    # Ownership = the position (org + node), not the actuation instance — a re-actuated node
    # keeps working its open assignment (E6; provenance stays on the row's actuation_id).
    if a.orgId != rec.orgId or a.nodeId != rec.nodeId:
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
    a = work_store.current_assignment(rec.orgId, rec.nodeId)
    if a is None:
        return JSONResponse(content=None)  # nothing to do — the runtime idles
    brief = work_store.get_brief(a.id)
    meter = ledger.get_meter(a.meterId) if a.meterId else None
    return {
        "assignment": a.model_dump(),
        "brief": brief.model_dump() if brief else None,
        "contract": {"kind": a.contractKind, "type": a.contractType},
        "memory": [m.entry for m in work_store.get_memory(rec.orgId, rec.nodeId)],
        "meter": meter.model_dump() if meter else None,
        # Undelivered notes, stamped delivered_at by this very read (amendment D-5) — advisory
        # context for the next turn, never a suspension.
        "notes": [n.model_dump() for n in work_store.take_undelivered_notes(a.id)],
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
    a = work_store.current_assignment(rec.orgId, rec.nodeId)
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
                session_span_id=body.sessionSpanId, settle=body.settle, model=body.model,
                cache_read_tokens=body.cacheReadTokens,
                cache_creation_tokens=body.cacheCreationTokens,
            )
        elif body.kind == "stage-update":
            if body.stageIdx is None or body.stageState is None:
                return _work_conflict(WorkError("stage-update needs stageIdx and stageState"))
            engine.update_stage(body.assignmentId, body.stageIdx, body.stageState)
        elif body.kind == "awaiting-reports":
            # The manager's turn boundary after a fan-out (engine.md §2 9a/11a): closes any
            # proposed batch into its plan-review gate, or arms/re-arms the await gate.
            engine.finish_turn(body.assignmentId)
        elif body.kind == "session-ref":
            # The cli-claude adapter stores the stream-json init session id as the resume
            # handle (cli-runtime.md §1) — a gated assignment is a suspended conversation.
            if not body.sessionRef:
                return _work_conflict(WorkError("session-ref needs sessionRef"))
            work_store.set_session_ref(body.assignmentId, body.sessionRef,
                                       transcript_path=body.transcriptPath)
        elif body.kind == "session-health":
            # F14: the adapter's liveness report — any stream event is proof of life; a
            # session dead with a provider error carries the cause for the sweep to surface.
            if not body.health:
                return _work_conflict(WorkError("session-health needs health"))
            engine.report_session_health(body.assignmentId, body.health, body.healthDetail)
        elif body.kind == "delivering":
            pass  # advisory; the deliverable is submitted via /dp/finish
        else:
            return _work_conflict(WorkError(f"unknown event kind {body.kind!r}"))
    except WorkError as exc:
        return _work_conflict(exc)
    return work_store.get_assignment(body.assignmentId).model_dump()


@router.post("/delegate")
def delegate(
    body: DelegateBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    """Managers: create a child assignment on a direct report (engine.md §2). Buffers as
    ``proposed`` when the caller's assignment is checkpointed (X3)."""
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        child = engine.delegate(
            body.assignmentId, body.reportNodeId, body.brief, refs=body.refs,
            contract_kind=body.contractKind, contract_type=body.contractType,
            depends_on=[d.model_dump(exclude_none=True) for d in body.dependsOn],
        )
    except WorkError as exc:
        return _work_conflict(exc)
    return child.model_dump()


def _reviewable(work_store, rec, assignment_id: str):
    """(assignment, None) if the caller manages it — acceptance decisions travel manager →
    report, so the target's PARENT assignment must belong to the caller's node."""
    a = work_store.get_assignment(assignment_id)
    if a is None:
        return None, JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND",
                                  "message": f"no assignment {assignment_id}"}})
    parent = work_store.get_assignment(a.parentId) if a.parentId else None
    if parent is None or parent.orgId != rec.orgId or parent.nodeId != rec.nodeId:
        return None, JSONResponse(status_code=403, content={"error": {"code": "NOT_YOUR_REPORT",
                                  "message": "assignment is not a report's work under the caller"}})
    return a, None


@router.post("/accept")
def accept_deliverable(
    body: ReviewBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _reviewable(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        a = engine.accept(body.assignmentId, note=body.note or None)
    except WorkError as exc:
        return _work_conflict(exc)
    return a.model_dump()


@router.post("/reject")
def reject_deliverable(
    body: ReviewBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _reviewable(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        a = engine.reject(body.assignmentId, body.note, revised_brief=body.revisedBrief)
    except WorkError as exc:
        return _work_conflict(exc)
    return a.model_dump()


class RepoCheckoutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    ref: str | None = None  # None => rw worktree (code.repo.write); set => ro checkout at ref


class RepoPrBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    testOutput: str = ""


class RepoMergeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignmentId: str
    branch: str


def _effective_grants(rec, actuator, engine) -> set[str]:
    """The caller's grant keys: from the compiled charter when actuated; pre-charter, from the
    chart's role via the catalog (same fallback the MCP surface uses)."""
    charter = actuator.get_charter(rec.actuationId, rec.nodeId)
    if charter is not None:
        return set(charter.get("toolGrants") or [])
    try:
        from ..catalog import get_catalog

        org = engine.orgs.read(rec.orgId)
        agent = next((a for a in org.agents if a.id == rec.nodeId), None)
        role = next((r for r in get_catalog().roles if agent and r.key == agent.role.key), None)
        return set(getattr(role, "toolGrants", []) or [])
    except Exception:  # noqa: BLE001 - no chart => no grants
        return set()


# Either write grant opens the rw worktree/PR path: code.repo.write is the tier-2 code grant,
# docs.repo.write the tier-1 docs re-scope (E8) — same git-mediated executor, same canopy/*
# branch discipline.
_REPO_WRITE_GRANTS = ("code.repo.write", "docs.repo.write")


def _grant_denied(work_store, rec, tool: str, need: str, assignment_id: str | None):
    work_store.record_tool_event(
        org_id=rec.orgId, actuation_id=rec.actuationId, node_id=rec.nodeId,
        assignment_id=assignment_id, tool=tool, outcome="denied",
        detail=f"missing grant {need}",
    )
    return JSONResponse(status_code=403, content={"error": {
        "code": "GRANT_DENIED", "message": f"this action needs the {need!r} grant"}})


@router.post("/repo/checkout")
def repo_checkout(
    body: RepoCheckoutBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
    actuator=Depends(get_actuator),
    repos=Depends(get_repos),
) -> Any:
    """The repo executors' intake surface (mvp.md §2): rw materializes a worktree on a
    canopy/<assignmentId> branch (code.repo.write); ro checks out a submitted head
    (repo.read)."""
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    grants = _effective_grants(rec, actuator, engine)
    try:
        if body.ref is None:
            if not grants.intersection(_REPO_WRITE_GRANTS):
                return _grant_denied(work_store, rec, "repo_checkout", "code.repo.write", a.id)
            result = repos.materialize_worktree(a.orgId, a.id)
        else:
            if "repo.read" not in grants:
                return _grant_denied(work_store, rec, "repo_checkout", "repo.read", a.id)
            result = repos.readonly_checkout(a.orgId, body.ref, tag=a.id)
    except RepoError as exc:
        return _work_conflict(WorkError(str(exc)))
    work_store.record_tool_event(
        org_id=rec.orgId, actuation_id=rec.actuationId, node_id=rec.nodeId,
        assignment_id=a.id, tool="repo_checkout", outcome="ok",
        detail=body.ref or "rw-worktree",
    )
    return result


@router.post("/repo/pr")
def repo_pr(
    body: RepoPrBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
    actuator=Depends(get_actuator),
    repos=Depends(get_repos),
) -> Any:
    """Assemble the PullRequest artifact from the worktree state (the engineer's finish)."""
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    grants = _effective_grants(rec, actuator, engine)
    if not grants.intersection(_REPO_WRITE_GRANTS):
        return _grant_denied(work_store, rec, "repo_pr", "code.repo.write", a.id)
    try:
        pr = repos.assemble_pr(a.orgId, a.id, test_output=body.testOutput)
    except RepoError as exc:
        return _work_conflict(WorkError(str(exc)))
    meta = engine.put_artifact(
        a.id, "pull-request", "PullRequest",
        json.dumps(pr, indent=2).encode("utf-8"), filename="pull-request.json",
    )
    work_store.record_tool_event(
        org_id=rec.orgId, actuation_id=rec.actuationId, node_id=rec.nodeId,
        assignment_id=a.id, tool="repo_pr", outcome="ok", detail=pr["headSha"],
    )
    return {"ref": meta.ref, "pr": pr}


@router.post("/repo/merge-request")
def repo_merge_request(
    body: RepoMergeBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
    actuator=Depends(get_actuator),
) -> Any:
    """The governed action (repo.merge grant): opens an ApprovalGate carrying the merge; the
    operator's approval runs the merge executor and records the attestation (invariant 9)."""
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    grants = _effective_grants(rec, actuator, engine)
    if "repo.merge" not in grants:
        return _grant_denied(work_store, rec, "repo_merge_request", "repo.merge", a.id)
    try:
        gate = engine.open_governed_action(
            a.id, "repo-merge", {"orgId": a.orgId, "branch": body.branch},
        )
    except WorkError as exc:
        return _work_conflict(exc)
    work_store.record_tool_event(
        org_id=rec.orgId, actuation_id=rec.actuationId, node_id=rec.nodeId,
        assignment_id=a.id, tool="repo_merge_request", outcome="ok", detail=body.branch,
    )
    return gate.model_dump()


@router.get("/reports/status")
def reports_status(
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    ledger=Depends(get_ledger),
) -> Any:
    """R1: the caller's children under its current assignment — states, cursors, meters, open
    gates (engine.md §5; the MCP `reports_status` tool serves the same view)."""
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    a = work_store.current_assignment(rec.orgId, rec.nodeId)
    if a is None:
        return {"reports": []}
    out = []
    for c in work_store.list_children(a.id):
        plan = work_store.get_plan(c.id)
        cursor = next((s.idx for s in plan.stages if s.state == "active"), None) if plan else None
        meter = ledger.get_meter(c.meterId) if c.meterId else None
        gates = work_store.list_gates(assignment_id=c.id, state="open")
        out.append({
            "assignmentId": c.id, "nodeId": c.nodeId, "state": c.state,
            "planCursor": cursor,
            "meter": {"spent": meter.spent, "allowance": meter.allowance} if meter else None,
            "openGates": [g.kind for g in gates],
        })
    return {"reports": out}


@router.post("/gates")
def open_gate(
    body: GateOpenBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    """Agent-side gate opening: clarification (intake feasibility failed) or escalation (asking
    above the pay grade). Approval-request gates arrive with governed actions in E3."""
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _owned(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        if body.kind == "clarification":
            gate = engine.open_clarification(body.assignmentId, body.question)
        elif body.kind == "escalation":
            gate = engine.open_escalation(body.assignmentId, body.question, refs=body.refs)
        else:
            return _work_conflict(WorkError(f"unknown gate kind {body.kind!r}"))
    except WorkError as exc:
        return _work_conflict(exc)
    return gate.model_dump()


@router.post("/priority")
def set_priority(
    body: PriorityBody,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    work_store=Depends(get_work_store),
    engine=Depends(get_engine),
) -> Any:
    """R3: a manager reprioritizes a report's assignment (higher first, FIFO within equal)."""
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    _a, err = _reviewable(work_store, rec, body.assignmentId)
    if err is not None:
        return err
    try:
        a = engine.set_priority(body.assignmentId, body.priority)
    except WorkError as exc:
        return _work_conflict(exc)
    return a.model_dump()


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
    work_store=Depends(get_work_store),
) -> Any:
    token = _bearer(authorization)
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return _unauthorized()
    meta = artifacts.resolve(ref)
    if meta is None or meta.orgId != rec.orgId:
        return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND",
                            "message": f"no artifact {ref}"}})
    # Grant check (workspace.md §2, the E3 wall): a node reads its OWN outputs and refs
    # explicitly granted via its briefs — nothing else, even inside its org.
    if meta.nodeId != rec.nodeId and ref not in work_store.refs_granted_to(
        rec.orgId, rec.nodeId
    ):
        return JSONResponse(status_code=403, content={"error": {"code": "GRANT_DENIED",
                            "message": f"ref {ref} is not in the caller's granted set"}})
    content = artifacts.read(ref)
    return {"meta": meta.model_dump(),
            "contentBase64": base64.b64encode(content).decode() if content else None}
