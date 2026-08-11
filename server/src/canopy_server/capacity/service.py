"""Capacity service — the glue between sessions and the ledger (C2).

A session's limit-signal arrives on the dp (the runtime forwards S1/S2 raw; adapters
interpret). The service resolves which ProviderAccount the session rides on — binding →
profile → account — dispatches to that account's adapter, records the readings, and
keeps the feed honest (every signal lands on the event feed with its team attached,
even the level-less pressure ones).
"""

from __future__ import annotations

from typing import Any

from .accounts import ProviderAccount, ProviderAccountStore
from .adapters import SessionSignal, adapter_for
from .ledger import CapacityLedger


class CapacityService:
    def __init__(self, accounts: ProviderAccountStore, ledger: CapacityLedger,
                 profiles, *, enabled) -> None:
        self.accounts = accounts
        self.ledger = ledger
        self.profiles = profiles
        self._enabled = enabled  # callable — config is read per call, not frozen at boot

    def account_for_session(self, team_id: str, node_id: str) -> ProviderAccount | None:
        binding = self.profiles.get_binding_for_node(team_id, node_id)
        profile = self.profiles.get_profile(binding.profileId) if binding else None
        if profile is None:
            return None
        account_id = getattr(profile, "providerAccountId", None)
        if account_id:
            acct = self.accounts.get(account_id)
            if acct is not None:
                return acct
        if profile.provider == "mock":
            return self.accounts.ensure_mock_account()
        return self.accounts.ensure_cli_account(profile.provider)

    def ingest_session_signal(self, team_id: str, node_id: str,
                              payload: dict[str, Any]) -> int:
        """Feed one dp `limit-signal` event through the account's adapter.
        Returns the number of readings recorded (0 = pressure/no-op)."""
        if not self._enabled():
            return 0
        account = self.account_for_session(team_id, node_id)
        if account is None:
            return 0
        adapter = adapter_for(account)
        if adapter is None:
            return 0
        ev = SessionSignal(
            signal=str(payload.get("signal", "")),
            text=payload.get("text"),
            error=payload.get("error"),
            error_status=payload.get("errorStatus"),
            retry_delay_ms=payload.get("retryDelayMs"),
            payload=payload,
        )
        readings = adapter.on_session_event(account, ev)
        for reading in readings:
            self.ledger.record_reading(account.id, reading)
            self.ledger.record_event(
                account.id,
                "window-exhausted" if reading.state_hint == "exhausted"
                else "window-reading",
                window_key=reading.window_key, team_id=team_id,
                payload={"source": reading.source, "detail": reading.detail,
                         "utilizationPct": reading.utilization_pct,
                         "resetsAt": reading.resets_at},
            )
        if not readings and ev.signal == "api_retry" and ev.error == "rate_limit":
            # S2: provider throttling before window exhaustion — pressure is a fact for
            # the feed, never a level for a gauge (03 §2; F11's rule).
            self.ledger.record_event(
                account.id, "rate-limit-pressure", team_id=team_id,
                payload={"errorStatus": ev.error_status,
                         "retryDelayMs": ev.retry_delay_ms},
            )
        return len(readings)
