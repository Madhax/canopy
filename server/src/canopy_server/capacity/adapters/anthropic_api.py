"""`anthropic` api-key accounts — token buckets from rate-limit headers (03 §2 tail).

[Official]: every Messages API response carries
``anthropic-ratelimit-{requests,input-tokens,output-tokens}-{limit,remaining,reset}``
plus ``retry-after`` on 429 — genuine tier-1 token-bucket windows. This adapter turns
one response's headers into readings; they arrive as ``response-headers`` session
signals through the same ingest path every other signal uses.

Wiring note: the gateway's Anthropic provider calls through the SDK, which hides
headers unless the call goes via ``with_raw_response`` — and the api-key path is
dormant in every current install (the operator runs subscription CLI). The raw-response
hook lands when the api-key rung is first exercised live; until then this adapter is
the parsing contract, CI-covered so the wiring is a two-line change, not a design one.
"""

from __future__ import annotations

import re

from ..accounts import ProviderAccount
from . import QuotaAdapter, SessionSignal, WindowReading, WindowSpec, register_adapter

WINDOWS = [
    WindowSpec("requests_min", "token-bucket", "Requests / min"),
    WindowSpec("input_tokens_min", "token-bucket", "Input tokens / min"),
    WindowSpec("output_tokens_min", "token-bucket", "Output tokens / min"),
]

_HEADER_WINDOWS = {
    "requests": "requests_min",
    "input-tokens": "input_tokens_min",
    "output-tokens": "output_tokens_min",
}

_AUTH_RE = re.compile(r"authentication|invalid.*api key|unauthorized|401", re.I)
_RATE_RE = re.compile(r"rate.?limit|429", re.I)
_TRANSIENT_RE = re.compile(r"overloaded|529|capacity", re.I)


def readings_from_headers(headers: dict[str, str]) -> list[WindowReading]:
    """``anthropic-ratelimit-*`` triplets → utilization readings. Reset timestamps
    are RFC 3339 per the docs and pass through verbatim (the provider's clock wins,
    06 §6.6); a bucket with a zero/absent limit yields no reading."""
    lower = {k.lower(): v for k, v in headers.items()}
    readings: list[WindowReading] = []
    for header_kind, window_key in _HEADER_WINDOWS.items():
        limit_raw = lower.get(f"anthropic-ratelimit-{header_kind}-limit")
        remaining_raw = lower.get(f"anthropic-ratelimit-{header_kind}-remaining")
        if limit_raw is None or remaining_raw is None:
            continue
        try:
            limit, remaining = int(limit_raw), int(remaining_raw)
        except ValueError:
            continue
        if limit <= 0:
            continue
        readings.append(WindowReading(
            window_key=window_key, source="provider-read", kind="token-bucket",
            utilization_pct=max(0.0, min(100.0, 100.0 * (limit - remaining) / limit)),
            resets_at=lower.get(f"anthropic-ratelimit-{header_kind}-reset"),
            detail="ratelimit-headers",
        ))
    return readings


@register_adapter("anthropic:api-key")
class AnthropicApiAdapter(QuotaAdapter):
    def expected_windows(self, account: ProviderAccount) -> list[WindowSpec]:
        return list(WINDOWS)

    def on_session_event(
        self, account: ProviderAccount, ev: SessionSignal
    ) -> list[WindowReading]:
        if ev.signal != "response-headers":
            return []
        headers = ev.payload.get("headers")
        return readings_from_headers(headers) if isinstance(headers, dict) else []

    def classify_error(self, account: ProviderAccount, text: str) -> str:
        if _AUTH_RE.search(text):
            return "auth"
        if _RATE_RE.search(text):
            # Token buckets refill in seconds; a 429 here is pressure, not a shut
            # window — retry-after is the provider's own backoff advice.
            return "capacity-transient"
        if _TRANSIENT_RE.search(text):
            return "capacity-transient"
        return "other"
