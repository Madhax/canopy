"""Neutral request/result schema + the provider and gateway ABCs.

One neutral ``CompletionRequest``/``CompletionResult`` shape crosses every boundary; each provider
adapter maps it to and from its SDK. The agent runtime is therefore provider-blind — it cannot
name a model, a provider, or a key (agent-profile.md §4). Tools are declared in one neutral schema
and provider-formatted by the adapters, so tool definitions live in exactly one place (risk AR-2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# A Step is coordination (decompose/await/synthesize) or production (the actual work). Tagging it
# lets the ledger report an "overhead %" — what fraction of spend is the org talking to itself
# (risk SC-1). The agent's loop knows which it is doing and sets this per call.
StepKind = Literal["coordination", "production"]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str  # "user" | "assistant" | "tool"
    content: str


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = ""
    inputSchema: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: str = ""
    messages: list[Message] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)
    maxOutputTokens: int = 4096
    temperature: float = 0.7
    providerOptions: dict[str, Any] = Field(default_factory=dict)


class CompletionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = ""
    toolCalls: list[ToolCall] = Field(default_factory=list)
    inputTokens: int = 0
    outputTokens: int = 0
    stopReason: str = "end_turn"
    providerRaw: dict[str, Any] = Field(default_factory=dict)  # truncated, debugging only


class ValidationResult(BaseModel):
    ok: bool
    error: str | None = None


class ModelInfo(BaseModel):
    id: str
    label: str = ""


class Step(BaseModel):
    """A metered model call (control-plane.md §4). One Step == one SpendEvent."""

    id: str
    actuationId: str
    nodeId: str
    taskId: str | None = None
    provider: str
    model: str
    kind: StepKind = "production"
    inputTokens: int
    outputTokens: int
    durationMs: int
    stopReason: str
    deltaNote: str | None = None
    createdAt: str


class ModelProvider(ABC):
    """Adapter to one provider SDK. Stateless — the credential is passed per call, never held."""

    key: str

    @abstractmethod
    async def complete(self, req: CompletionRequest, cred: str | None, *, model: str,
                       endpoint: str | None) -> CompletionResult: ...

    @abstractmethod
    async def validate(self, *, model: str, cred: str | None,
                       endpoint: str | None) -> ValidationResult:
        """A cheap liveness ping used at actuation readiness (agent-profile.md §3)."""

    def list_known_models(self) -> list[ModelInfo]:
        return []


class ModelGateway(ABC):
    @abstractmethod
    async def complete(self, run_token: str, req: CompletionRequest, *,
                       kind: StepKind = "production", task_id: str | None = None) -> Any: ...

    @abstractmethod
    async def validate_profile(self, profile_id: str) -> ValidationResult: ...
