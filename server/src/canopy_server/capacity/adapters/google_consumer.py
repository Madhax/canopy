"""`google-consumer` — Google AI plan accounts (03 §3). Tiers 2–3 BY CONSTRUCTION.

The honest headline, from the design: no server-side "remaining quota" read exists for
consumer Google AI plans, and this adapter says so out loud rather than laundering
estimates into gauges. What it ships (CAP-D5 keeps it to exactly this until a
``cli-gemini`` runtime exists):

- **Classification** of 429 shapes: an API-style ``RESOURCE_EXHAUSTED`` whose
  QuotaFailure names a *daily* quota exhausts ``cli_daily`` with reset at next
  midnight PT (RetryInfo is documented-unreliable for daily exhaustion — ignored
  there, honored for per-minute); bare capacity 429s ("no capacity for model …")
  are ``capacity-transient`` — backoff without touching windows. Indistinguishable
  dimensions stay transient: we refuse to invent precision the payload doesn't carry.
- **Local counting against the known denominator**: ``cli_daily`` has a published
  per-plan denominator (1,500/day AI Pro, 2,000/day AI Ultra), the one place this
  adapter can count meaningfully client-side. A count signal yields an *inferred*
  reading with an honest basis (``~n/1500 · counted locally``); external usage of
  the same Google login is invisible until a 429 corrects us — stated, not hidden.

The app windows (``app_five_hour``, ``app_weekly``) are schema-only: relative,
compute-weighted, mutable without notice — they render "no reading yet" until an
event arrives, which is correct (06 §6.3).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from ..accounts import ProviderAccount
from . import QuotaAdapter, SessionSignal, WindowReading, WindowSpec, register_adapter

WINDOWS = [
    WindowSpec("cli_daily", "fixed-daily", "CLI daily"),
    WindowSpec("app_five_hour", "rolling-window", "App (5 h)"),
    WindowSpec("app_weekly", "rolling-window", "App weekly"),
]

#: Published per-plan daily request quotas (03 §3, [Official]); keyed by planHint.
DAILY_DENOMINATORS = {"ai-pro": 1500, "ai-ultra": 2000}

_EXHAUSTED_RE = re.compile(r"RESOURCE_EXHAUSTED|quota", re.I)
_DAILY_RE = re.compile(r"per\s*day|daily|PerDay", re.I)
_MINUTE_RE = re.compile(r"per\s*minute|PerMinute", re.I)
_TRANSIENT_RE = re.compile(r"no capacity|overloaded|unavailable", re.I)
_AUTH_RE = re.compile(r"unauthenticated|unauthorized|credential|login|forbidden", re.I)


def next_midnight_pt(now: datetime) -> str:
    """``cli_daily`` resets at midnight Pacific. zoneinfo when the tz database is
    present; a fixed PST approximation otherwise (Windows without tzdata) — an hour
    of DST error on a daily reset beats refusing to state one."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Los_Angeles")
    except Exception:  # noqa: BLE001 - no tzdata on this host
        tz = timezone(timedelta(hours=-8))
    local = now.astimezone(tz)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0,
                                                   microsecond=0)
    return midnight.astimezone(UTC).isoformat().replace("+00:00", "Z")


@register_adapter("google:subscription-cli")
class GoogleConsumerAdapter(QuotaAdapter):
    def expected_windows(self, account: ProviderAccount) -> list[WindowSpec]:
        return list(WINDOWS)

    def on_session_event(
        self, account: ProviderAccount, ev: SessionSignal
    ) -> list[WindowReading]:
        now = self._now_of(ev)
        if ev.signal == "gemini-request-count":
            # The counting schema (03 §3): a cli-gemini runtime (future) reports the
            # day's Canopy-issued request count; the denominator is plan-published.
            count = ev.payload.get("countToday")
            denom = DAILY_DENOMINATORS.get(account.planHint or "")
            if count is None or not denom:
                return []
            return [WindowReading(
                window_key="cli_daily", source="inferred", kind="fixed-daily",
                utilization_pct=min(100.0, 100.0 * int(count) / denom),
                resets_at=next_midnight_pt(now),
                detail=f"counted-locally {int(count)}/{denom}",
            )]
        if ev.signal == "session-result" and ev.text:
            if _EXHAUSTED_RE.search(ev.text) and _DAILY_RE.search(ev.text):
                return [WindowReading(
                    window_key="cli_daily", source="provider-event", kind="fixed-daily",
                    utilization_pct=100.0, resets_at=next_midnight_pt(now),
                    detail="quota-failure-daily", state_hint="exhausted",
                )]
        return []

    @staticmethod
    def _now_of(ev: SessionSignal) -> datetime:
        """Reset arithmetic is clock-driven where possible: a signal may carry its
        observation time (tests always do); wall clock is the live fallback."""
        raw = ev.payload.get("observedAt")
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(UTC)

    def classify_error(self, account: ProviderAccount, text: str) -> str:
        if _EXHAUSTED_RE.search(text) and _DAILY_RE.search(text):
            return "quota-exhausted"
        if _EXHAUSTED_RE.search(text) and _MINUTE_RE.search(text):
            # Per-minute buckets refill in seconds — honor RetryInfo, back off,
            # never touch a daily window (03 §3).
            return "capacity-transient"
        if _AUTH_RE.search(text):
            return "auth"
        if _TRANSIENT_RE.search(text) or _EXHAUSTED_RE.search(text):
            return "capacity-transient"
        return "other"
