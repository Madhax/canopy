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
from .orgs import parse_budget

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

# The org ceiling warns at this fraction before it refuses (01 §6: warn, then refuse).
BUDGET_WARN_FRACTION = 0.8


def week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC — the admission week the org ceiling spans (01 §6)."""
    return (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)


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
            # C5 fairness (04 §6) — NEW spawns only, like K2: a suspended
            # conversation resuming is not a new session, and running work is
            # never evicted by a share or a watermark.
            if assignment is not None and assignment.state in _PRE_SESSION_STATES:
                above = self._above_reserve_watermark(account)
                if above is not None and sched.priority != "interactive":
                    return Admission(admit=False, reason="reserve-watermark",
                                     payload={"pool": account.id, **above,
                                              "policy": "hold-resume"})
                held = self._check_contention(assignment, account,
                                              interactive_only=above is not None)
                if held is not None:
                    return held
        return Admission(admit=True)

    # ------------------------------------------------- fairness (C5, 04 §6)
    def _above_reserve_watermark(self, account) -> dict | None:
        """K8 (02 §6): above ``100 − reserve`` pool utilization, only interactive
        teams are admitted — headroom pre-provisioned by policy, not emergency
        knob-turning. v1 approximation, documented: the binding watermark is the
        largest reserve any org holds on this pool, and interactive teams of ANY
        org are admitted above it; per-org reserve *depth* accounting waits for a
        real multi-reserve case (01 §9). Returns the payload facts when above the
        watermark, else None; no reading means no watermark (admission never
        blocks on ignorance, 04 §7)."""
        reserve = self._max_reserve(account.id)
        if reserve <= 0:
            return None
        util = self._pool_utilization(account.id)
        if util is None or util < 100.0 - reserve:
            return None
        return {"reason": "reserve-watermark",
                "watermarkPct": round(100.0 - reserve, 1), "utilizationPct": util}

    def _check_contention(self, assignment: Assignment, account, *,
                          interactive_only: bool) -> Admission | None:
        """K7 + the per-account etiquette cap (04 §3 note, §6). Shares only bind
        under contention — idle share flows to whoever has work; when spawn demand
        exceeds free account slots, ordering is reserve eligibility → org shares
        (unconsumed claim this window) → team priority → FIFO by wait time."""
        cap = account.maxConcurrentSessions
        if not cap or cap <= 0:
            return None
        active = self._active_on_account(account)
        free = cap - active
        if free <= 0:
            return Admission(admit=False, reason="account-session-cap", payload={
                "pool": account.id, "reason": "account-session-cap",
                "cap": cap, "active": active, "policy": "hold-resume",
            })
        claimants = self._spawn_claimants(account)
        if interactive_only:
            # Reserve eligibility is the FIRST ordering key: ineligible (batch)
            # claimants cannot take a slot above the watermark, so they must not
            # occupy a rank that starves an eligible team.
            claimants = [c for c in claimants if c["priority"] == "interactive"]
        if len(claimants) <= free:
            return None
        ranked = self._rank_claimants(claimants, account)
        if assignment.id in {c["assignmentId"] for c in ranked[:free]}:
            return None
        position = next((i for i, c in enumerate(ranked)
                         if c["assignmentId"] == assignment.id), None)
        return Admission(admit=False, reason="share-contention", payload={
            "pool": account.id, "reason": "share-contention",
            "position": position, "freeSlots": free,
            "claimants": len(ranked), "policy": "hold-resume",
        })

    def _rank_claimants(self, claimants: list[dict], account) -> list[dict]:
        """04 §6 ordering, deterministically. Org claim = normalized share minus
        the org's consumed fraction of Canopy's burn this window — an org with
        pent-up demand accumulates claim while idle, so starvation is bounded.
        Slots interleave across orgs in claim order (weighted round-robin), so one
        hungry org cannot take every slot in a single pass."""
        shares = self._org_shares(account.id)
        consumed = self._org_consumed_fraction(account)
        org_ids = sorted({c["orgId"] for c in claimants if c["orgId"]})
        configured = [shares[o] for o in org_ids if o in shares]
        # Unset orgs weigh in at the configured mean — turning K7 on for one org
        # must not zero everyone else's claim.
        default = (sum(configured) / len(configured)) if configured else 1.0
        weights = {o: shares.get(o, default) for o in org_ids}
        total = sum(weights.values()) or 1.0
        deficit = {o: weights[o] / total - consumed.get(o, 0.0) for o in org_ids}
        prio = {"interactive": 0, "batch": 1}
        queues = {
            o: sorted(
                (c for c in claimants if c["orgId"] == o),
                key=lambda c: (prio.get(c["priority"], 1), c["waitingSince"]),
            )
            for o in org_ids
        }
        # The §6 chain, total-ordered: shares decide; on an exact tie, the next
        # keys decide — the org whose head claimant is interactive, then the
        # longest-waiting head, then org id so the order is never clock-dependent.
        order = sorted(
            org_ids,
            key=lambda o: (-deficit[o], prio.get(queues[o][0]["priority"], 1),
                           queues[o][0]["waitingSince"], o),
        )
        ranked: list[dict] = []
        while any(queues.values()):
            for o in order:
                if queues[o]:
                    ranked.append(queues[o].pop(0))
        return ranked

    def _spawn_claimants(self, account) -> list[dict]:
        marks = ",".join("?" for _ in _PRE_SESSION_STATES)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT a.id AS id, a.team_id AS team_id, a.node_id AS node_id,"
                f" a.created_at AS created_at, t.organization_id AS org_id"
                f" FROM work_assignment a JOIN teams t ON t.id = a.team_id"
                f" WHERE a.state IN ({marks}) ORDER BY a.created_at",
                tuple(_PRE_SESSION_STATES),
            ).fetchall()
        out: list[dict] = []
        cache: dict[tuple[str, str], str | None] = {}
        for r in rows:
            key = (r["team_id"], r["node_id"])
            if key not in cache:
                acct = self.capacity.account_for_session(*key)
                cache[key] = acct.id if acct is not None else None
            if cache[key] != account.id:
                continue
            out.append({
                "assignmentId": r["id"], "teamId": r["team_id"],
                "nodeId": r["node_id"], "orgId": r["org_id"],
                "waitingSince": r["created_at"] or "",
                "priority": self.get(r["team_id"]).priority,
            })
        return out

    def _active_on_account(self, account) -> int:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT team_id, node_id FROM work_assignment WHERE state = 'executing'"
            ).fetchall()
        cache: dict[tuple[str, str], str | None] = {}
        n = 0
        for r in rows:
            key = (r["team_id"], r["node_id"])
            if key not in cache:
                acct = self.capacity.account_for_session(*key)
                cache[key] = acct.id if acct is not None else None
            if cache[key] == account.id:
                n += 1
        return n

    def _max_reserve(self, account_id: str) -> float:
        return max(
            (b.reserveWatermarkPct.get(account_id, 0.0) for _, b in self._org_budgets()),
            default=0.0,
        )

    def _org_shares(self, account_id: str) -> dict[str, float]:
        return {
            org_id: b.capacityShares[account_id]
            for org_id, b in self._org_budgets()
            if account_id in b.capacityShares
        }

    def _org_budgets(self) -> list[tuple[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT id, budget_json FROM organization").fetchall()
        return [(r["id"], parse_budget(json.loads(r["budget_json"] or "{}"))) for r in rows]

    def _pool_utilization(self, account_id: str) -> float | None:
        """The pool's binding level: the highest known utilization across the
        account-wide (unscoped) windows. Unknown beats fabricated — no reading,
        no watermark (admission never blocks on ignorance, 04 §7)."""
        utils = [
            w["utilization_pct"] for w in self.ledger.windows(account_id)
            if not w.get("model_scope") and w.get("utilization_pct") is not None
            and w.get("source")
        ]
        return max(utils) if utils else None

    def _org_consumed_fraction(self, account) -> dict[str, float]:
        """Each org's fraction of Canopy's own attributed burn on the pool's
        busiest window over the attribution horizon — the 'consumed share this
        window' the WRR weighs against (04 §6). External burn is the operator's,
        not any org's, and is deliberately absent."""
        best: dict[str, float] = {}
        best_total = 0.0
        for w in self.ledger.windows(account.id):
            if w.get("source") is None:
                continue
            rates = self.ledger.burn_rates(account.id, w["key"])
            rates.pop("external", None)
            total = sum(rates.values())
            if total <= best_total:
                continue
            by_org: dict[str, float] = {}
            for team_id, pp in rates.items():
                org_id = self._team_org_id(team_id)
                if org_id:
                    by_org[org_id] = by_org.get(org_id, 0.0) + pp
            best = {o: pp / total for o, pp in by_org.items()}
            best_total = total
        return best

    def _team_org_id(self, team_id: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT organization_id FROM teams WHERE id = ?", (team_id,)
            ).fetchone()
        return row["organization_id"] if row is not None else None

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

    # ------------------------------------------- boundary 3: intent admission (C5)
    def admit_intent(self, team_id: str) -> Admission:
        """The org weekly ceiling (01 §6) at ``POST /api/teams/{id}/intents``.
        An *admission* budget, not a meter: crossing it refuses NEW intents for
        the rest of the week; it never hard-stops an executing assignment (that
        remains the assignment meter's job). Estimated dollars — the only honest
        cross-provider unit — so the refusal message says "estimated"."""
        if not self._enabled():
            return Admission(admit=True, reason="capacity-disabled")
        org = self._org_of_team(team_id)
        if org is None:
            return Admission(admit=True)
        ceiling = parse_budget(org["budget"]).weeklyCostCeilingUsd
        if not ceiling:
            return Admission(admit=True)
        now = datetime.fromisoformat(self._now().replace("Z", "+00:00"))
        start = week_start(now)
        since = start.isoformat().replace("+00:00", "Z")
        spent_usd = self._org_week_spend_micros(org["id"], since) / 1e6
        payload = {
            "orgId": org["id"], "orgKey": org["key"],
            "weekSpendUsd": round(spent_usd, 2), "ceilingUsd": ceiling,
            "weekResetsAt": (start + timedelta(days=7)).isoformat()
            .replace("+00:00", "Z"),
        }
        if spent_usd >= ceiling:
            return Admission(admit=False, reason="org-budget", payload=payload)
        if spent_usd >= BUDGET_WARN_FRACTION * ceiling:
            return Admission(admit=True, reason="org-budget-approaching",
                             payload=payload)
        return Admission(admit=True)

    def org_economics(self, org_id: str) -> dict[str, Any]:
        """The org's budget posture for read surfaces (console K7/K8 read-only rows,
        the org page editor): stored claims + derived week spend, computed here so
        no view invents its own week arithmetic."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, key, budget_json FROM organization WHERE id = ?", (org_id,)
            ).fetchone()
        if row is None:
            return {}
        budget = parse_budget(json.loads(row["budget_json"] or "{}"))
        now = datetime.fromisoformat(self._now().replace("Z", "+00:00"))
        start = week_start(now)
        since = start.isoformat().replace("+00:00", "Z")
        return {
            "weekSpendUsd": round(self._org_week_spend_micros(org_id, since) / 1e6, 2),
            "weeklyCostCeilingUsd": budget.weeklyCostCeilingUsd,
            "weekStartedAt": since,
            "weekResetsAt": (start + timedelta(days=7)).isoformat()
            .replace("+00:00", "Z"),
            "capacityShares": budget.capacityShares,
            "reserveWatermarkPct": budget.reserveWatermarkPct,
        }

    def _org_of_team(self, team_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT o.id AS id, o.key AS key, o.budget_json AS budget_json"
                " FROM organization o JOIN teams t ON t.organization_id = o.id"
                " WHERE t.id = ?",
                (team_id,),
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "key": row["key"],
                "budget": json.loads(row["budget_json"] or "{}")}

    def _org_week_spend_micros(self, org_id: str, since: str) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(e.est_cost_micros), 0) AS micros"
                " FROM ledger_spend_event e JOIN teams t ON t.id = e.team_id"
                " WHERE t.organization_id = ? AND e.created_at >= ?",
                (org_id, since),
            ).fetchone()
        return int(row["micros"] or 0)

    # ----------------------------------------------------- the what-if strip (C5)
    def what_if(self, account_id: str, *, window_key: str | None = None,
                needed_pp: float | None = None, by: str | None = None) -> dict[str, Any]:
        """06 §3: "which knob frees how much" as a computation, not head math.
        Enumerates per-team knob moves (K1 pause, K2 sessions→1, K3 pace 50%) and
        what each frees over the horizon, from the SAME attribution math as the
        prediction chips — the strip and the scheduler can never disagree.
        Nothing here applies anything; Apply is one explicit click per suggestion."""
        windows = [w for w in self.ledger.windows(account_id) if w.get("source")]
        if window_key is None:
            burn_by_window = {
                w["key"]: sum(
                    r for t, r in self.ledger.burn_rates(account_id, w["key"]).items()
                    if t != "external"
                )
                for w in windows
            }
            window_key = max(burn_by_window, key=burn_by_window.get, default=None) \
                if burn_by_window else None
        if window_key is None:
            return {"accountId": account_id, "windowKey": None, "suggestions": [],
                    "basis": "no-burn"}

        now = datetime.fromisoformat(self._now().replace("Z", "+00:00"))
        horizon_h = 1.0
        horizon_basis = "default-1h"
        if by:
            try:
                target = datetime.fromisoformat(str(by).replace("Z", "+00:00"))
                horizon_h = max(0.0, (target - now).total_seconds() / 3600.0)
                horizon_basis = "by-time"
            except ValueError:
                pass
        else:
            w = next((w for w in windows if w["key"] == window_key), None)
            resets = w.get("resets_at") if w else None
            if resets:
                try:
                    reset_dt = datetime.fromisoformat(str(resets).replace("Z", "+00:00"))
                    horizon_h = max(0.0, (reset_dt - now).total_seconds() / 3600.0)
                    horizon_basis = "until-reset"
                except ValueError:
                    pass

        rates = self.ledger.burn_rates(account_id, window_key)
        rates.pop("external", None)
        candidates: list[dict[str, Any]] = []
        for team_id, burn in sorted(rates.items(), key=lambda kv: -kv[1]):
            if burn <= 0:
                continue
            sched = self.get(team_id)
            candidates.append({
                "action": {"teamId": team_id, "knob": "runState", "value": "paused"},
                "label": "pause", "freesPpHr": round(burn, 2),
            })
            active = self._active_sessions(team_id, exclude_node="")
            if active > 1:
                candidates.append({
                    "action": {"teamId": team_id, "knob": "maxConcurrentSessions",
                               "value": 1},
                    "label": f"sessions {active}→1",
                    "freesPpHr": round(burn * (active - 1) / active, 2),
                })
            chunk = sched.paceChunkTurns or 4
            candidates.append({
                "action": {"teamId": team_id, "knob": "pace",
                           "value": {"paceChunkTurns": chunk,
                                     "paceDelayS": chunk * 60}},
                "label": "pace 50%", "freesPpHr": round(burn * 0.5, 2),
                "basis": "duty-cycle estimate (60 s/turn assumed)",
            })

        def suggestion(actions: list[dict[str, Any]]) -> dict[str, Any]:
            frees_hr = round(sum(a["freesPpHr"] for a in actions), 2)
            frees = round(frees_hr * horizon_h, 2)
            return {
                "actions": [{**a["action"], "label": a["label"],
                             "freesPpHr": a["freesPpHr"]} for a in actions],
                "freesPpHr": frees_hr, "freesPp": frees,
                "satisfies": (frees >= needed_pp) if needed_pp is not None else None,
            }

        suggestions = [suggestion([c]) for c in candidates]
        if needed_pp is not None and not any(s["satisfies"] for s in suggestions):
            # The cheapest sufficient combo: greedy over the biggest levers, at most
            # one knob per team (pausing a team subsumes pacing it).
            combo: list[dict[str, Any]] = []
            seen_teams: set[str] = set()
            for c in sorted(candidates, key=lambda c: -c["freesPpHr"]):
                if c["action"]["teamId"] in seen_teams:
                    continue
                combo.append(c)
                seen_teams.add(c["action"]["teamId"])
                if sum(x["freesPpHr"] for x in combo) * horizon_h >= needed_pp:
                    break
            if combo:
                suggestions.append(suggestion(combo))
        if needed_pp is not None:
            # Satisfying moves first, least-disruptive (smallest sufficient) leading.
            suggestions.sort(key=lambda s: (not s["satisfies"], s["freesPp"]
                                            if s["satisfies"] else -s["freesPp"]))
        else:
            suggestions.sort(key=lambda s: -s["freesPp"])
        return {
            "accountId": account_id, "windowKey": window_key,
            "horizonH": round(horizon_h, 2), "horizonBasis": horizon_basis,
            "neededPp": needed_pp, "basis": "ewma-attribution",
            "suggestions": suggestions,
        }
