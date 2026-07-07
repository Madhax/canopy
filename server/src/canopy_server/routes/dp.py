"""Data plane API (``/api/dp/*``) — run-token auth only, loopback-bound in v1.

This is the surface agents call. In A1 only the Model Gateway lives here (``llm/complete``); A2
adds ``register``/``heartbeat``/``charter``, A3 ``a2a/{targetNodeId}``. Auth is the per-agent run
token in the ``Authorization: Bearer`` header — an agent can act only as itself (sandbox.md §5).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..deps import get_gateway
from ..gateway.base import CompletionRequest, Message, StepKind, ToolSpec
from ..gateway.service import GatewayBudgetExhausted, GatewayError

router = APIRouter(prefix="/dp")


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
