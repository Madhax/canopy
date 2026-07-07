"""Model Gateway — the only path from an agent to an LLM API (topology.md §1).

Agents never call Anthropic/Gemini directly; they call the gateway with a run token. The gateway
resolves the node's binding → profile → secret, checks the budget *before dispatch*, meters the
call as a Step, emits a SpendEvent, and returns a provider-blind result. This mechanically
satisfies invariants 7 (no work without a meter) and 10 (credentials never enter an agent).
"""

from __future__ import annotations

from .base import (
    CompletionRequest,
    CompletionResult,
    Message,
    ModelGateway,
    ModelInfo,
    ModelProvider,
    Step,
    StepKind,
    ToolCall,
    ToolSpec,
    ValidationResult,
)
from .providers import provider_registry
from .service import DefaultModelGateway, GatewayResult

__all__ = [
    "CompletionRequest",
    "CompletionResult",
    "DefaultModelGateway",
    "GatewayResult",
    "Message",
    "ModelGateway",
    "ModelInfo",
    "ModelProvider",
    "Step",
    "StepKind",
    "ToolCall",
    "ToolSpec",
    "ValidationResult",
    "provider_registry",
]
