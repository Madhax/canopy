"""The capacity ledger (02-capacity-model §3–§5): windows, append-only readings with
three tiers of truth, the event feed, and the derived math — attribution, burn rates,
runway.

The invariant of the whole layer: a capacity number always carries its **tier and age**.
The window's current state is the *most authoritative recent* reading, never merely the
newest; inferred levels only ever interpolate between provider anchors. All time flows
through the injected clock — runway/reset math is never ``now()``-scattered (07 §6).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..db import Db, register_schema
from ..ids import new_capacity_event_id, new_reading_id, new_window_id
from .adapters import WindowReading

SCHEMA = """
CREATE TABLE IF NOT EXISTS capacity_window (
    id             TEXT PRIMARY KEY,
    account_id     TEXT NOT NULL,
    key            TEXT NOT NULL,
    kind           TEXT NOT NULL DEFAULT 'rolling-window',
    model_scope    TEXT,
    display_name   TEXT NOT NULL DEFAULT '',
    utilization_pct REAL,
    resets_at      TEXT,
    state          TEXT NOT NULL DEFAULT 'unknown',
    source         TEXT,
    observed_at    TEXT,
    UNIQUE(account_id, key)
);
CREATE TABLE IF NOT EXISTS capacity_reading (
    id              TEXT PRIMARY KEY,
    window_id       TEXT NOT NULL,
    utilization_pct REAL,
    resets_at       TEXT,
    source          TEXT NOT NULL,
    detail          TEXT NOT NULL DEFAULT '',
    observed_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reading_window ON capacity_reading (window_id, observed_at);
CREATE TABLE IF NOT EXISTS capacity_event (
    id           TEXT PRIMARY KEY,
    account_id   TEXT NOT NULL,
    window_key   TEXT,
    org_id       TEXT,
    team_id      TEXT,
    kind         TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_capacity_event ON capacity_event (account_id, created_at);
"""
register_schema(SCHEMA)

_TIER_RANK = {"provider-read": 3, "provider-event": 2, "inferred": 1}

WARN_PCT = 80.0


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


class CapacityLedger:
    def __init__(self, db: Db, *, now, reading_ttl_s: int = 900,
                 attribution_window_s: int = 3600):
        self.db = db
        db.ensure_schema()  # idempotent; direct construction (tests) predates route imports
        self._now = now  # -> ISO string (the injected clock; FakeClock in tests)
        self.reading_ttl_s = reading_ttl_s
        self.attribution_window_s = attribution_window_s

    # ------------------------------------------------------------------ windows
    def ensure_window(self, account_id: str, key: str, *, kind: str = "rolling-window",
                      model_scope: str | None = None, display_name: str = "") -> str:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id FROM capacity_window WHERE account_id=? AND key=?",
                (account_id, key),
            ).fetchone()
            if row is not None:
                return row["id"]
            wid = new_window_id()
            conn.execute(
                "INSERT INTO capacity_window (id, account_id, key, kind, model_scope,"
                " display_name) VALUES (?,?,?,?,?,?)",
                (wid, account_id, key, kind, model_scope, display_name or key),
            )
            return wid

    def windows(self, account_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM capacity_window WHERE account_id=? ORDER BY key",
                (account_id,),
            ).fetchall()
        return [self._window_view(dict(r)) for r in rows]

    def window(self, account_id: str, key: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM capacity_window WHERE account_id=? AND key=?",
                (account_id, key),
            ).fetchone()
        return self._window_view(dict(row)) if row else None

    def _window_view(self, w: dict[str, Any]) -> dict[str, Any]:
        """Effective state on read: an exhausted window whose provider-stated reset has
        passed decays to ok-with-unknown-level (the provider's clock is the truth)."""
        now = _parse_ts(self._now())
        resets = _parse_ts(w.get("resets_at"))
        if w.get("state") == "exhausted" and now is not None and resets is not None \
                and now >= resets:
            w = {**w, "state": "ok", "utilization_pct": None,
                 "source": "inferred", "detail": "reset-passed"}
        age_s = None
        observed = _parse_ts(w.get("observed_at"))
        if now is not None and observed is not None:
            age_s = max(0, int((now - observed).total_seconds()))
        w["age_s"] = age_s
        return w

    # ----------------------------------------------------------------- readings
    def record_reading(self, account_id: str, reading: WindowReading) -> str:
        """Append the reading and update the window's denormalized state by authority:
        a reading wins if its tier outranks the current one, ties on tier and is newer,
        or the current state has gone stale (tier-1 freshness decays after the TTL)."""
        wid = self.ensure_window(account_id, reading.window_key, kind=reading.kind)
        observed = self._now()
        rid = new_reading_id()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO capacity_reading (id, window_id, utilization_pct, resets_at,"
                " source, detail, observed_at) VALUES (?,?,?,?,?,?,?)",
                (rid, wid, reading.utilization_pct, reading.resets_at, reading.source,
                 reading.detail, observed),
            )
            w = dict(conn.execute(
                "SELECT * FROM capacity_window WHERE id=?", (wid,)
            ).fetchone())
            if self._reading_wins(w, reading, observed):
                state = self._state_of(reading)
                conn.execute(
                    "UPDATE capacity_window SET utilization_pct=?, resets_at=?, state=?,"
                    " source=?, observed_at=? WHERE id=?",
                    (reading.utilization_pct,
                     reading.resets_at or (w.get("resets_at") if state != "ok" else None),
                     state, reading.source, observed, wid),
                )
        return rid

    def _reading_wins(self, w: dict[str, Any], reading: WindowReading,
                      observed: str) -> bool:
        current_tier = _TIER_RANK.get(w.get("source") or "", 0)
        new_tier = _TIER_RANK.get(reading.source, 0)
        if new_tier > current_tier:
            return True
        if new_tier == current_tier:
            return True  # same authority, newer information
        prev = _parse_ts(w.get("observed_at"))
        now = _parse_ts(observed)
        if prev is None or now is None:
            return True
        return (now - prev).total_seconds() > self.reading_ttl_s  # stale → accept lower tier

    @staticmethod
    def _state_of(reading: WindowReading) -> str:
        if reading.state_hint in ("ok", "exhausted", "warning"):
            return reading.state_hint
        if reading.utilization_pct is None:
            return "unknown"
        if reading.utilization_pct >= 100.0:
            return "exhausted"
        if reading.utilization_pct >= WARN_PCT:
            return "warning"
        return "ok"

    # -------------------------------------------------------------------- feed
    def record_event(self, account_id: str, kind: str, *, window_key: str | None = None,
                     org_id: str | None = None, team_id: str | None = None,
                     payload: dict[str, Any] | None = None) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO capacity_event (id, account_id, window_key, org_id, team_id,"
                " kind, payload_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (new_capacity_event_id(), account_id, window_key, org_id, team_id, kind,
                 json.dumps(payload or {}), self._now()),
            )

    def events(self, account_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM capacity_event WHERE account_id=?"
                " ORDER BY created_at DESC, id DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        return [
            {**dict(r), "payload": json.loads(r["payload_json"])} for r in rows
        ]

    # ------------------------------------------------------- attribution + burn
    def attribution(self, account_id: str, window_key: str, *,
                    since: str, until: str | None = None) -> dict[str, Any]:
        """Who burned the window over [since, until] (02 §5).

        Level deltas come from consecutive **tier-1** readings; the split of each delta
        follows Canopy's own cache-aware step metering by team over the same interval;
        the residual is `external` — the operator's own usage, shown as its own band,
        never smeared across teams. Shares sum to the provider-measured delta exactly.
        """
        until = until or self._now()
        with self.db.connect() as conn:
            wrow = conn.execute(
                "SELECT id FROM capacity_window WHERE account_id=? AND key=?",
                (account_id, window_key),
            ).fetchone()
            if wrow is None:
                return {"deltaPct": 0.0, "teams": {}, "external": 0.0,
                        "basis": "no-window"}
            readings = conn.execute(
                "SELECT * FROM capacity_reading WHERE window_id=? AND source=?"
                " AND utilization_pct IS NOT NULL AND observed_at >= ? AND observed_at <= ?"
                " ORDER BY observed_at",
                (wrow["id"], "provider-read", since, until),
            ).fetchall()
        delta = 0.0
        for prev, cur in zip(readings, readings[1:], strict=False):
            step = cur["utilization_pct"] - prev["utilization_pct"]
            if step > 0:  # resets show as drops; only burn counts
                delta += step
        team_tokens = self._step_tokens_by_team(since, until)
        total_tokens = sum(team_tokens.values())
        teams: dict[str, float] = {}
        if delta > 0 and total_tokens > 0:
            # Canopy's own sessions can never have burned more than the provider says
            # the pool moved; the remainder is external by definition.
            canopy_share = min(1.0, self._canopy_fraction(team_tokens, delta))
            for team_id, tokens in team_tokens.items():
                teams[team_id] = delta * canopy_share * (tokens / total_tokens)
        external = max(0.0, delta - sum(teams.values()))
        return {
            "deltaPct": delta, "teams": teams, "external": external,
            "basis": f"tier1-deltas × step-split ({len(readings)} readings)",
            "since": since, "until": until,
        }

    @staticmethod
    def _canopy_fraction(team_tokens: dict[str, int], delta: float) -> float:
        """C2: without a fitted tokens-per-point calibration constant, all of the delta
        is provisionally attributable to whoever was active; calibration (02 §5) refines
        this from tier-1 anchors at C3+. With zero Canopy tokens the fraction is zero
        and the whole delta lands on `external`."""
        return 1.0 if team_tokens else 0.0

    def _step_tokens_by_team(self, since: str, until: str) -> dict[str, int]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT a.team_id AS team_id,"
                " SUM(s.input_tokens + s.output_tokens + s.cache_creation_tokens"
                "     + s.cache_read_tokens / 10) AS tokens"
                " FROM work_step s JOIN work_assignment a ON a.id = s.assignment_id"
                " WHERE s.created_at >= ? AND s.created_at <= ?"
                " GROUP BY a.team_id",
                (since, until),
            ).fetchall()
        return {r["team_id"]: int(r["tokens"] or 0) for r in rows if r["team_id"]}

    def burn_rates(self, account_id: str, window_key: str) -> dict[str, float]:
        """Per-team burn in percentage points per hour over the attribution horizon."""
        now = _parse_ts(self._now())
        assert now is not None
        since_dt = now.timestamp() - self.attribution_window_s
        since = datetime.fromtimestamp(since_dt, tz=UTC).isoformat().replace("+00:00", "Z")
        attr = self.attribution(account_id, window_key, since=since)
        hours = self.attribution_window_s / 3600.0
        rates = {t: pct / hours for t, pct in attr["teams"].items()}
        if attr["external"] > 0:
            rates["external"] = attr["external"] / hours
        return rates

    def runway(self, account_id: str, window_key: str) -> dict[str, Any]:
        """`exhausts ~T` at current burn — or None when idle/unknown (never invented)."""
        w = self.window(account_id, window_key)
        if w is None or w.get("utilization_pct") is None:
            return {"exhaustsAt": None, "basis": "no-level"}
        rates = self.burn_rates(account_id, window_key)
        total = sum(rates.values())
        if total <= 0:
            return {"exhaustsAt": None, "basis": "no-burn"}
        hours_left = (100.0 - float(w["utilization_pct"])) / total
        now = _parse_ts(self._now())
        assert now is not None
        exhausts = datetime.fromtimestamp(
            now.timestamp() + hours_left * 3600, tz=UTC
        ).isoformat().replace("+00:00", "Z")
        return {"exhaustsAt": exhausts, "burnPpHr": total, "basis": "ewma-burn"}
