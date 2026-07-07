"""Provider adapters: ``mock`` (default), ``anthropic``, ``gemini``.

The real adapters lazy-import their SDKs *inside* the call, so a missing SDK or a missing key can
never break the mock path — CI, the golden tests, and "try Canopy without an API key" all run
green offline (risk IM-2). Each frontier SDK is confined to its adapter (risk IM-4): an upgrade or
a swap touches one file, never the gateway or the runtime.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..registry import Registry
from .base import (
    CompletionRequest,
    CompletionResult,
    ModelInfo,
    ModelProvider,
    ToolCall,
    ValidationResult,
)

provider_registry: Registry[ModelProvider] = Registry("model provider")


class ProviderError(Exception):
    """A provider call failed (network, auth, 5xx). The gateway maps this to a retryable 502."""


def _est_tokens(text: str) -> int:
    # Deterministic, provider-agnostic rough token estimate (~4 chars/token).
    return max(1, len(text) // 4)


# --------------------------------------------------------------------------- #
# Mock — deterministic, free, keyless (the testing/demo spine, risk IM-2)
# --------------------------------------------------------------------------- #
@provider_registry.register("mock")
class MockProvider(ModelProvider):
    """A deterministic provider. Same input → same output and same token counts, always.

    Scriptable through ``providerOptions.mock`` so tests drive exact behavior without spend:
      * ``text``          — force the assistant text
      * ``output_tokens`` — force the output token count (e.g. to exhaust a meter precisely)
      * ``tool_calls``    — list of ``{name, arguments}`` to return as tool calls
      * ``stop_reason``   — force the stop reason
    A4 will extend this with matcher-keyed scripts (role + step) for full-fabric e2e.
    """

    key = "mock"

    async def complete(self, req: CompletionRequest, cred, *, model, endpoint) -> CompletionResult:
        opts: dict[str, Any] = dict(req.providerOptions.get("mock", {}))
        last_user = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), ""
        )
        text = opts.get("text")
        if text is None:
            digest = hashlib.sha256(last_user.encode("utf-8")).hexdigest()[:8]
            text = f"[mock:{model}] {last_user[:200]} (#{digest})"

        tool_calls = [
            ToolCall(
                id=f"mocktc_{i}",
                name=tc["name"],
                arguments=tc.get("arguments", {}),
            )
            for i, tc in enumerate(opts.get("tool_calls", []))
        ]
        stop_reason = opts.get("stop_reason", "tool_use" if tool_calls else "end_turn")

        in_tokens = _est_tokens(req.system) + sum(_est_tokens(m.content) for m in req.messages)
        out_tokens = int(opts["output_tokens"]) if "output_tokens" in opts else _est_tokens(text)
        return CompletionResult(
            text=text,
            toolCalls=tool_calls,
            inputTokens=in_tokens,
            outputTokens=out_tokens,
            stopReason=stop_reason,
            providerRaw={"mock": True},
        )

    async def validate(self, *, model, cred, endpoint) -> ValidationResult:
        return ValidationResult(ok=True)

    def list_known_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="mock-1", label="Mock (deterministic, free)")]


# --------------------------------------------------------------------------- #
# Anthropic — official `anthropic` SDK, Messages API
# --------------------------------------------------------------------------- #
@provider_registry.register("anthropic")
class AnthropicProvider(ModelProvider):
    key = "anthropic"

    def _client(self, cred: str | None, endpoint: str | None):
        if not cred:
            raise ProviderError("anthropic profile has no API key bound")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover - SDK is a declared dep
            raise ProviderError(f"anthropic SDK not available: {exc}") from exc
        return AsyncAnthropic(api_key=cred, base_url=endpoint or None)

    async def complete(self, req: CompletionRequest, cred, *, model, endpoint) -> CompletionResult:
        client = self._client(cred, endpoint)
        messages = [
            {"role": "assistant" if m.role == "assistant" else "user", "content": m.content}
            for m in req.messages
        ]
        tools = [
            {"name": t.name, "description": t.description,
             "input_schema": t.inputSchema or {"type": "object", "properties": {}}}
            for t in req.tools
        ]
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": req.maxOutputTokens,
            "temperature": req.temperature,
        }
        if req.system:
            kwargs["system"] = req.system
        if tools:
            kwargs["tools"] = tools
        try:
            resp = await client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize every SDK error to one type
            raise ProviderError(f"anthropic call failed: {exc}") from exc

        text_parts, tool_calls = [], []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
            elif getattr(block, "type", None) == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))
        return CompletionResult(
            text="".join(text_parts),
            toolCalls=tool_calls,
            inputTokens=resp.usage.input_tokens,
            outputTokens=resp.usage.output_tokens,
            stopReason=resp.stop_reason or "end_turn",
        )

    async def validate(self, *, model, cred, endpoint) -> ValidationResult:
        try:
            client = self._client(cred, endpoint)
            await client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return ValidationResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            return ValidationResult(ok=False, error=str(exc))

    def list_known_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="claude-opus-4-8", label="Claude Opus 4.8"),
            ModelInfo(id="claude-sonnet-5", label="Claude Sonnet 5"),
            ModelInfo(id="claude-haiku-4-5", label="Claude Haiku 4.5"),
        ]


# --------------------------------------------------------------------------- #
# Gemini — official `google-genai` SDK, generateContent
# --------------------------------------------------------------------------- #
@provider_registry.register("gemini")
class GeminiProvider(ModelProvider):
    key = "gemini"

    def _client(self, cred: str | None, endpoint: str | None):
        if not cred:
            raise ProviderError("gemini profile has no API key bound")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - SDK is a declared dep
            raise ProviderError(f"google-genai SDK not available: {exc}") from exc
        http_options = {"base_url": endpoint} if endpoint else None
        return genai.Client(api_key=cred, http_options=http_options)

    async def complete(self, req: CompletionRequest, cred, *, model, endpoint) -> CompletionResult:
        client = self._client(cred, endpoint)
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise ProviderError(f"google-genai SDK not available: {exc}") from exc

        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user",
                parts=[types.Part(text=m.content)],
            )
            for m in req.messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=req.system or None,
            max_output_tokens=req.maxOutputTokens,
            temperature=req.temperature,
        )
        try:
            resp = await client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"gemini call failed: {exc}") from exc

        usage = getattr(resp, "usage_metadata", None)
        return CompletionResult(
            text=resp.text or "",
            inputTokens=getattr(usage, "prompt_token_count", 0) or 0,
            outputTokens=getattr(usage, "candidates_token_count", 0) or 0,
            stopReason="end_turn",
        )

    async def validate(self, *, model, cred, endpoint) -> ValidationResult:
        try:
            client = self._client(cred, endpoint)
            from google.genai import types

            await client.aio.models.generate_content(
                model=model,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=1),
            )
            return ValidationResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            return ValidationResult(ok=False, error=str(exc))

    def list_known_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="gemini-2.5-pro", label="Gemini 2.5 Pro"),
            ModelInfo(id="gemini-2.5-flash", label="Gemini 2.5 Flash"),
        ]
