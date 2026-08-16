"""Quota adapters — reading the source of truth per provider (03-provider-quota-adapters).

An adapter turns provider surfaces into :class:`WindowReading`s for the capacity ledger.
``on_session_event`` is the mandatory, free path (tier 2, in-band on sessions Canopy
already parses); ``poll`` is optional tier-1 pull (C3+); ``classify_error`` keeps F11's
lesson one level up — a quota 429, a transient 429, and an auth failure demand three
different reactions. [Community] surfaces must degrade without operator action.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..accounts import ProviderAccount


@dataclass
class WindowSpec:
    key: str
    kind: str  # rolling-window | fixed-daily | token-bucket | credit-pool
    display_name: str
    model_scope: str | None = None


@dataclass
class WindowReading:
    """One piece of capacity knowledge, on its way into the append-only ledger."""

    window_key: str
    source: str  # provider-read | provider-event | inferred
    utilization_pct: float | None = None
    resets_at: str | None = None  # ISO timestamp
    detail: str = ""
    kind: str = "rolling-window"  # used only when the reading discovers the window
    state_hint: str | None = None  # ok | exhausted — for level-less events


@dataclass
class SessionSignal:
    """What the runtime forwards from a session's stream (dp `limit-signal` events)."""

    signal: str  # session-result | api_retry | mock-reading
    text: str | None = None
    error: str | None = None  # api_retry: rate_limit | overloaded | …
    error_status: int | None = None
    retry_delay_ms: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class QuotaAdapter(ABC):
    key: str

    def expected_windows(self, account: ProviderAccount) -> list[WindowSpec]:
        """Seed set for gauges-before-first-contact; discovery still rules (02 §3)."""
        return []

    def poll(self, account: ProviderAccount) -> list[WindowReading]:
        """Tier-1 pull; a no-op for providers with nothing to poll."""
        return []

    @abstractmethod
    def on_session_event(
        self, account: ProviderAccount, ev: SessionSignal
    ) -> list[WindowReading]: ...

    def classify_error(self, account: ProviderAccount, text: str) -> str:
        """→ 'quota-exhausted' | 'capacity-transient' | 'auth' | 'other'."""
        return "other"


_REGISTRY: dict[str, type[QuotaAdapter]] = {}


def register_adapter(key: str):
    def deco(cls: type[QuotaAdapter]) -> type[QuotaAdapter]:
        cls.key = key
        _REGISTRY[key] = cls
        return cls

    return deco


def adapter_for(account: ProviderAccount) -> QuotaAdapter | None:
    """Resolve by ``provider:auth_mode`` then ``provider``; None = unmetered provider."""
    for key in (f"{account.provider}:{account.authMode}", account.provider):
        cls = _REGISTRY.get(key)
        if cls is not None:
            return cls()
    return None


from . import (  # noqa: E402,F401  (registration side effects)
    anthropic_api,
    anthropic_max,
    google_consumer,
    mock,
)
