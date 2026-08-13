"""The portfolio scheduler — admission and pacing at boundaries Canopy already owns
(design/organizations/04, milestone C4).

Nothing here interferes mid-turn: the governor decides *whether a team should be running
right now* at exactly three server-owned boundaries (session spawn, turn/chunk boundary,
intent admission), and when work must stop for capacity it suspends behind an
InterventionGate with ``opened_by='trigger:capacity'`` — a **scheduled wait**, not a
stall and not an error (F11's classification discipline at the fleet level). Resumption
is a timer: the sweep resolves the gate when the provider's reset passes and admission
agrees. A paused team is a set of suspended conversations, not lost work.

Default posture is today's behavior: no schedule row = ``running``, uncapped, batch.
The whole module is inert while ``[capacity] enabled`` is false.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .db import Db, register_schema
from .engine.models import Assignment

SCHEMA = """
CREATE TABLE IF NOT EXISTS team_schedule (
    team_id                  TEXT PRIMARY KEY,
    run_state                TEXT NOT NULL DEFAULT 'running',
    max_concurrent_sessions  INTEGER,
    pace_chunk_turns         INTEGER,
    pace_delay_s             INTEGER,
    model_tier_cap           TEXT,
    priority                 TEXT NOT NULL DEFAULT 'batch',
    active_hours             TEXT,
    fallback_json            TEXT NOT NULL DEFAULT '["hold-resume"]',
    updated_at               TEXT
);
"""
register_schema(SCHEMA)

RUN_STATES = ("running", "paused", "drain")
PRIORITIES = ("interactive", "batch")
FALLBACK_RUNGS = ("hold-resume", "degrade-model", "switch-account", "extra-usage", "park")
_PRE_SESSION_STATES = {"created", "briefed", "intake", "planning"}


@dataclass
class Schedule:
    teamId: str
    runState: str = "running"
    maxConcurrentSessions: int | None = None
    paceChunkTurns: int | None = None
    paceDelayS: int | None = None
    modelTierCap: str | None = None
    priority: str = "batch"
    activeHours: str | None = None
    fallbackPolicy: list[str] = field(default_factory=lambda: ["hold-resume"])
    updatedAt: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "teamId": self.teamId, "runState": self.runState,
            "maxConcurrentSessions": self.maxConcurrentSessions,
            "paceChunkTurns": self.paceChunkTurns, "paceDelayS": self.paceDelayS,
            "modelTierCap": self.modelTierCap, "priority": self.priority,
            "activeHours": self.activeHours, "fallbackPolicy": self.fallbackPolicy,
            "updatedAt": self.updatedAt,
        }


@dataclass
class Admission:
    admit: bool
    reason: str = "ok"
    # the capacity-gate payload when holding (04 §4); also the dp hold body
    payload: dict[str, Any] = field(default_factory=dict)
    # degrade-model rung: the model the next chunk should run on (04 §5 rung 2)
    model_override: str | None = None


def _parse_hhmm(s: str) -> tuple[int, int] | None:
    try:
        h, m = s.strip().split(":")
        return int(h), int(m)
    except ValueError:
        return None


def in_active_hours(spec: str | None, now: datetime) -> bool:
    """``"HH:MM-HH:MM"`` daily window, server clock; wrap-around supported ("22:00-06:00")."""
    if not spec:
        return True
    parts = spec.split("-", 1)
    if len(parts) != 2:
        return True  # malformed specs never lock a team out
    start, end = _parse_hhmm(parts[0]), _parse_hhmm(parts[1])
    if start is None or end is None:
        return True
    cur = (now.hour, now.minute)
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end  # wraps midnight


class Scheduler:
    def __init__(self, db: Db, *, now, capacity_service, capacity_ledger, work_store,
                 gates, enabled, resume_jitter_s: int = 120):
        self.db = db
        db.ensure_schema()
        self._now = now  # -> ISO string (injected clock)
        self.capacity = capacity_service
        self.ledger = capacity_ledger
        self.work = work_store
        self.gates = gates
        self._enabled = enabled  # callable
        self.resume_jitter_s = resume_jitter_s

    # ------------------------------------------------------------- schedule CRUD
    def get(self, team_id: str) -> Schedule:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM team_schedule WHERE team_id = ?", (team_id,)
            ).fetchone()
        if row is None:
            return Schedule(teamId=team_id)  # the non-breaking default: today's behavior
        return Schedule(
            teamId=row["team_id"], runState=row["run_state"],
            maxConcurrentSessions=row["max_concurrent_sessions"],
            paceChunkTurns=row["pace_chunk_turns"], paceDelayS=row["pace_delay_s"],
            modelTierCap=row["model_tier_cap"], priority=row["priority"],
            activeHours=row["active_hours"],
            fallbackPolicy=json.loads(row["fallback_json"] or '["hold-resume"]'),
            updatedAt=row["updated_at"],
        )

    def put(self, schedule: Schedule) -> Schedule:
        schedule.updatedAt = self._now()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO team_schedule (team_id, run_state, max_concurrent_sessions,"
                " pace_chunk_turns, pace_delay_s, model_tier_cap, priority, active_hours,"
                " fallback_json, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(team_id) DO UPDATE SET run_state=excluded.run_state,"
                " max_concurrent_sessions=excluded.max_concurrent_sessions,"
                " pace_chunk_turns=excluded.pace_chunk_turns,"
                " pace_delay_s=excluded.pace_delay_s,"
                " model_tier_cap=excluded.model_tier_cap, priority=excluded.priority,"
                " active_hours=excluded.active_hours, fallback_json=excluded.fallback_json,"
                " updated_at=excluded.updated_at",
                (schedule.teamId, schedule.runState, schedule.maxConcurrentSessions,
                 schedule.paceChunkTurns, schedule.paceDelayS, schedule.modelTierCap,
                 schedule.priority, schedule.activeHours,
                 json.dumps(schedule.fallbackPolicy), schedule.updatedAt),
            )
        return schedule

    # ---------------------------------------------------------------- admission
    def check(self, team_id: str, node_id: str, assignment: Assignment | None) -> Admission:
        """Boundary 1+2 (04 §2): may this node run (or continue) work right now?"""
        if not self._enabled():
            return Admission(admit=True, reason="capacity-disabled")
        sched = self.get(team_id)

        if sched.runState == "paused":
            return Admission(admit=False, reason="paused",
                            payload={"reason": "paused", "policy": "operator"})
        if sched.runState == "drain" and assignment is not None \
                and assignment.state in _PRE_SESSION_STATES:
            return Admission(admit=False, reason="drain",
                            payload={"reason": "drain", "policy": "operator"})

        now = datetime.fromisoformat(self._now().replace("Z", "+00:00"))
        if not in_active_hours(sched.activeHours, now):
            return Admission(admit=False, reason="active-hours",
                            payload={"reason": "active-hours",
                                     "activeHours": sched.activeHours})

        # K2 — spawn cap: gates NEW sessions only; running work is never evicted by a cap.
        if (sched.maxConcurrentSessions is not None and assignment is not None
                and assignment.state in _PRE_SESSION_STATES):
            active = self._active_sessions(team_id, exclude_node=node_id)
            if active >= sched.maxConcurrentSessions:
                return Admission(admit=False, reason="session-cap",
                                payload={"reason": "session-cap",
                                         "cap": sched.maxConcurrentSessions})

        # Window exhaustion → the fallback ladder (04 §5, C4 rungs 1–2).
        account = self.capacity.account_for_session(team_id, node_id)
        if account is not None:
            exhausted = [w for w in self.ledger.windows(account.id)
                         if w["state"] == "exhausted"]
            binding = self._binding_window(exhausted, sched)
            if binding is not None:
                cap = (sched.modelTierCap or "").lower()
                scope = (binding.get("model_scope") or "").lower()
                cap_is_the_exhausted_tier = bool(cap) and (cap in scope or scope in cap)
                if (scope and "degrade-model" in sched.fallbackPolicy
                        and sched.modelTierCap and not cap_is_the_exhausted_tier):
                    # Only a model-scoped window is shut; the chunk restarts on the
                    # fallback tier, same account (rung 2). A Directive records it.
                    return Admission(admit=True, reason="degrade-model",
                                    model_override=sched.modelTierCap)
                return Admission(admit=False, reason="window-exhausted", payload={
                    "pool": account.id, "window": binding["key"],
                    "reason": "exhausted", "resetsAt": binding.get("resets_at"),
                    "policy": "hold-resume",
                })
        return Admission(admit=True)

    @staticmethod
    def _binding_window(exhausted: list[dict], sched: Schedule) -> dict | None:
        """Which exhausted window actually binds this team's next session? Account-wide
        (null scope) windows always bind; model-scoped ones bind unless the team is
        already capped at/under a different tier (C4 approximation: scoped windows bind
        when no tier cap routes around them)."""
        for w in exhausted:
            if not w.get("model_scope"):
                return w
        for w in exhausted:
            if w.get("model_scope") and not sched.modelTierCap:
                return w
        for w in exhausted:
            if w.get("model_scope") and sched.modelTierCap \
                    and sched.modelTierCap.lower() in (w.get("model_scope") or "").lower():
                return w
        # A scoped window is exhausted but the tier cap routes around it (degrade case).
        return exhausted[0] if exhausted and all(
            not w.get("model_scope") for w in exhausted) else (
            exhausted[0] if exhausted and not any(True for _ in ()) else None)

    def _active_sessions(self, team_id: str, *, exclude_node: str) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT node_id) AS n FROM work_assignment"
                " WHERE team_id = ? AND state = 'executing' AND node_id != ?",
                (team_id, exclude_node),
            ).fetchone()
        return int(row["n"] or 0)

    # ------------------------------------------------------------ capacity gates
    def hold(self, assignment: Assignment, admission: Admission) -> None:
        """Suspend live work behind the capacity gate (04 §4). Idempotent per reason —
        the gate table's partial unique index absorbs repeated boundary checks."""
        if assignment.state in ("gated",) or assignment.state in _PRE_SESSION_STATES:
            return  # pre-session work just waits at admission; no gate to record
        self.gates.open(
            assignment, "intervention", opened_by="trigger:capacity", owner="operator",
            reason=f"capacity:{admission.reason}:{admission.payload.get('window', '')}",
            payload=admission.payload,
        )

    def sweep(self) -> int:
        """Timer auto-resolution (04 §4): resolve capacity gates whose provider reset has
        passed (plus jitter) — including resets that passed while the control plane was
        down. A gate with unknown ``resetsAt`` resolves when its window reads ok again.
        Returns the number of gates resolved."""
        if not self._enabled():
            return 0
        resolved = 0
        now = datetime.fromisoformat(self._now().replace("Z", "+00:00"))
        for gate in self.work.list_open_gates_by_opener("trigger:capacity"):
            payload = gate.payload
            a = self.work.get_assignment(gate.assignmentId)
            if a is None:
                continue
            reason = str(payload.get("reason", ""))
            if reason in ("paused", "drain", "active-hours", "session-cap"):
                # Operator/clock holds resolve when admission passes again.
                if self.check(a.teamId, a.nodeId, None).admit:
                    self.gates.resolve(gate, resolution={"action": "resume",
                                                         "by": "trigger:capacity"},
                                       resolved_by="system")
                    resolved += 1
                continue
            resets = payload.get("resetsAt")
            due = False
            if resets:
                try:
                    reset_dt = datetime.fromisoformat(str(resets).replace("Z", "+00:00"))
                    due = now >= reset_dt + timedelta(seconds=self.resume_jitter_s)
                except ValueError:
                    due = False
            if not resets or not due:
                # Unknown reset: the window recovering (ok/unknown) is the signal.
                pool, window = payload.get("pool"), payload.get("window")
                if pool and window:
                    w = self.ledger.window(pool, window)
                    due = w is not None and w["state"] in ("ok", "unknown", "warning")
            if due and self.check(a.teamId, a.nodeId, None).admit:
                self.gates.resolve(gate, resolution={"action": "resume",
                                                     "by": "trigger:capacity"},
                                   resolved_by="system")
                self.ledger.record_event(
                    str(payload.get("pool") or "unknown"), "hold-resumed",
                    window_key=payload.get("window"), team_id=a.teamId,
                    payload={"assignmentId": a.id})
                resolved += 1
        return resolved

    # ---------------------------------------------------------------- predictions
    def predictions(self, team_id: str) -> dict[str, Any]:
        """The knob panel's chips (04 §3, K1–K3): pp/hr from the attribution model,
        labeled with the basis. Zero math in the UI."""
        sched = self.get(team_id)
        account = None
        burn = 0.0
        window_key = None
        # Find the team's burn on its account's headline window.
        node = self._any_node(team_id)
        if node is not None:
            account = self.capacity.account_for_session(team_id, node)
        if account is not None:
            for w in self.ledger.windows(account.id):
                if w["source"] is None:
                    continue
                rates = self.ledger.burn_rates(account.id, w["key"])
                if team_id in rates:
                    burn = rates[team_id]
                    window_key = w["key"]
                    break
        out: dict[str, Any] = {"windowKey": window_key, "basis": "ewma-attribution"}
        out["pauseFreesPpHr"] = round(burn, 2)  # K1
        active = max(1, self._active_sessions(team_id, exclude_node=""))
        if sched.maxConcurrentSessions and sched.maxConcurrentSessions < active:
            removed = active - sched.maxConcurrentSessions
            out["sessionCapFreesPpHr"] = round(burn * removed / active, 2)  # K2
        if sched.paceChunkTurns and sched.paceDelayS:
            # Duty-cycle math with an assumed chunk duration of 60 s/turn — honest error
            # bars belong to the console copy; the basis says "estimate".
            chunk_s = sched.paceChunkTurns * 60
            out["paceFreesPpHr"] = round(
                burn * sched.paceDelayS / (chunk_s + sched.paceDelayS), 2)  # K3
            out["paceBasis"] = "duty-cycle estimate (60 s/turn assumed)"
        return out

    def _any_node(self, team_id: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT agent_node_id FROM profiles_binding WHERE team_id = ? LIMIT 1",
                (team_id,),
            ).fetchone()
        return row["agent_node_id"] if row else None
