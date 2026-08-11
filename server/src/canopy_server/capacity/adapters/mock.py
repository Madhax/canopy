"""`mock` — scriptable capacity for CI and demos (03 §4).

The capacity analog of the scriptable mock ModelProvider: readings arrive as explicit
``mock-reading`` session signals, so every scheduler and console behavior is demonstrable
keyless and deterministically (pillar 1).
"""

from __future__ import annotations

from ..accounts import ProviderAccount
from . import QuotaAdapter, SessionSignal, WindowReading, register_adapter


@register_adapter("mock")
class MockQuotaAdapter(QuotaAdapter):
    def on_session_event(
        self, account: ProviderAccount, ev: SessionSignal
    ) -> list[WindowReading]:
        if ev.signal != "mock-reading":
            return []
        p = ev.payload
        return [
            WindowReading(
                window_key=str(p.get("windowKey", "mock_window")),
                source=str(p.get("source", "provider-read")),
                utilization_pct=p.get("utilizationPct"),
                resets_at=p.get("resetsAt"),
                detail="mock",
                kind=str(p.get("kind", "rolling-window")),
                state_hint=p.get("stateHint"),
            )
        ]

    def classify_error(self, account: ProviderAccount, text: str) -> str:
        return "quota-exhausted" if "quota" in text.lower() else "other"
