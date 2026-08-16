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
                 profiles, *, enabled, notify=None) -> None:
        self.accounts = accounts
        self.ledger = ledger
        self.profiles = profiles
        self._enabled = enabled  # callable — config is read per call, not frozen at boot
        # notify(team_id, severity, kind, text, dedupe_key) — WorkStore.notify in prod.
        self._notify = notify

    def account_for_session(self, team_id: str, node_id: str) -> ProviderAccount | None:
        binding = self.profiles.get_binding_for_node(team_id, node_id)
        profile = self.profiles.get_profile(binding.profileId) if binding else None
        if profile is None:
            return None
        return self.account_for_profile(profile)

    def account_for_profile(self, profile) -> ProviderAccount | None:
        """Profile → account resolution (02 §2): the account carries auth, the
        profile carries model choice. Also the switch-account rung's map from a
        chain entry to the pool it would draw on (04 §5 rung 3)."""
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
            before = self.ledger.window(account.id, reading.window_key)
            prior_state = before["state"] if before else "unknown"
            self.ledger.record_reading(account.id, reading)
            self._maybe_notify(account, reading, prior_state, team_id)
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

    def _maybe_notify(self, account, reading, prior_state: str, team_id: str) -> None:
        """The 06 §5 vocabulary, house severity discipline intact: exhaustion is NOT an
        emergency (`info` — the governor dresses for scheduled weather); the warning
        watermark is a `warning`. Deduped per window+reset so a signal storm is one row."""
        if self._notify is None:
            return
        after = self.ledger.window(account.id, reading.window_key)
        if after is None or after["state"] == prior_state:
            return
        window = after.get("display_name") or reading.window_key
        resets = after.get("resets_at")
        if after["state"] == "exhausted":
            text = f"{account.label}: {window} window exhausted"
            if resets:
                text += f" · resets {resets}"
            else:
                text += " · reset unknown (resolves on next successful call)"
            self._notify(team_id, "info", "capacity-exhausted", text,
                         dedupe_key=f"cap-exh:{account.id}:{reading.window_key}:{resets}")
        elif after["state"] == "warning" and prior_state in ("ok", "unknown"):
            pct = after.get("utilization_pct")
            if pct is not None:
                text = f"{account.label}: {window} window at {pct:.0f}%"
            else:
                text = f"{account.label}: {window} window near its limit"
            self._notify(team_id, "warning", "capacity-warning", text,
                         dedupe_key=f"cap-warn:{account.id}:{reading.window_key}:{resets}")
