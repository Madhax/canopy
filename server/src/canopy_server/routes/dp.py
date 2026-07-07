"""Data plane API (``/api/dp/*``) — run-token auth only, loopback-bound in v1.

This is the surface agents call. A1: the Model Gateway (``llm/complete``). A2: ``charter`` fetch,
``register``, ``heartbeat``. A3: ``a2a/{targetNodeId}``. Auth is the per-agent run token in the
``Authorization: Bearer`` header — an agent can act only as itself (sandbox.md §5).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..deps import get_actuator, get_directory, get_gateway, get_runtokens
from ..gateway.base import CompletionRequest, Message, StepKind, ToolSpec
from ..gateway.service import GatewayBudgetExhausted, GatewayError

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
