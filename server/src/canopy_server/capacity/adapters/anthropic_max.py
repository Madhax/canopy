"""`anthropic-max` — the subscription-CLI account (03 §2), C2 slice: S1 + S2.

S1 [Community, stable in practice]: when a subscription limit hits in headless mode the
final ``result`` carries either the legacy machine shape
``"Claude AI usage limit reached|<epoch-seconds>"`` or the interactive phrasing
``"You've hit your session limit · resets 3:45pm"`` (weekly / Opus variants). Both parse;
unparseable limit text degrades to `five_hour` exhausted with unknown reset (conservative).

S2 [Official]: ``system/api_retry`` events carry ``error ∈ {rate_limit, overloaded, …}``;
`rate_limit` is a *pressure* signal, never a level — it feeds the event feed, not a gauge.

S3 (statusline tap) lands at C3; S4 (usage endpoint, ToS-gray, off-default) at C6.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ..accounts import ProviderAccount
from . import QuotaAdapter, SessionSignal, WindowReading, WindowSpec, register_adapter

WINDOWS = [
    WindowSpec("five_hour", "rolling-window", "Session (5 h)"),
    WindowSpec("seven_day", "rolling-window", "Weekly"),
    WindowSpec("seven_day_opus", "rolling-window", "Weekly · Opus", model_scope="opus"),
    WindowSpec("seven_day_sonnet", "rolling-window", "Weekly · Sonnet", model_scope="sonnet"),
]

# S1 shape A — legacy machine-parseable: "Claude AI usage limit reached|1754899200"
_PIPE_RE = re.compile(r"Claude AI usage limit reached\|(\d{9,12})", re.I)
# S1 shape B — interactive phrasing: "You've hit your session limit · resets 3:45pm"
_HIT_RE = re.compile(
    r"you'?ve hit your (session|weekly|opus(?:\s+weekly)?|5-hour) limit", re.I
)
# Generic limit language (conservative fallback)
_GENERIC_RE = re.compile(r"usage limit|limit reached|session limit|weekly limit", re.I)
_AUTH_RE = re.compile(r"authentication|unauthorized|api key|login|credential", re.I)
_TRANSIENT_RE = re.compile(r"overloaded|529|capacity", re.I)

_KIND_TO_WINDOW = {
    "session": "five_hour",
    "5-hour": "five_hour",
    "weekly": "seven_day",
    "opus": "seven_day_opus",
    "opus weekly": "seven_day_opus",
}


def parse_limit_text(text: str) -> WindowReading | None:
    """S1: map a result-error string onto an exhaustion reading, or None if not a limit."""
    m = _PIPE_RE.search(text)
    if m:
        resets = datetime.fromtimestamp(int(m.group(1)), tz=UTC).isoformat()
        return WindowReading(
            window_key="five_hour", source="provider-event", utilization_pct=100.0,
            resets_at=resets.replace("+00:00", "Z"), detail="s1-pipe", state_hint="exhausted",
        )
    m = _HIT_RE.search(text)
    if m:
        kind = re.sub(r"\s+", " ", m.group(1).lower())
        window = _KIND_TO_WINDOW.get(kind, "five_hour")
        # The human phrasing's reset time ("resets 3:45pm") has no date or timezone —
        # refusing to guess is the honest move; exhaustion pins state, reset stays unknown.
        return WindowReading(
            window_key=window, source="provider-event", utilization_pct=100.0,
            resets_at=None, detail="s1-phrase", state_hint="exhausted",
        )
    if _GENERIC_RE.search(text):
        return WindowReading(
            window_key="five_hour", source="provider-event", utilization_pct=100.0,
            resets_at=None, detail="s1-generic", state_hint="exhausted",
        )
    return None


@register_adapter("anthropic:subscription-cli")
class AnthropicMaxAdapter(QuotaAdapter):
    def expected_windows(self, account: ProviderAccount) -> list[WindowSpec]:
        return list(WINDOWS)

    def on_session_event(
        self, account: ProviderAccount, ev: SessionSignal
    ) -> list[WindowReading]:
        if ev.signal == "session-result":
            if ev.text and not ev.error and not ev.payload.get("isError", True):
                # A successful result is proof the door is open — a level-less OK event
                # (this is what flips an exhausted window back after its reset passes).
                return [WindowReading(window_key="five_hour", source="provider-event",
                                      detail="session-ok", state_hint="ok")]
            reading = parse_limit_text(ev.text or "")
            return [reading] if reading else []
        if ev.signal == "session-ok":
            return [WindowReading(window_key="five_hour", source="provider-event",
                                  detail="session-ok", state_hint="ok")]
        # S2: pressure, not level — the service records it on the feed; no reading.
        return []

    def classify_error(self, account: ProviderAccount, text: str) -> str:
        if parse_limit_text(text) is not None:
            return "quota-exhausted"
        if _AUTH_RE.search(text):
            return "auth"
        if _TRANSIENT_RE.search(text):
            return "capacity-transient"
        return "other"
