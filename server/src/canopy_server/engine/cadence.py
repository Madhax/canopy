"""Cadence scheduler (engine.md §4) — "put this team on a schedule".

A cadence is ``{cron, intent_text, node}`` on an team. A 30 s lifespan loop (same pattern as the
reconciler) calls :meth:`CadenceScheduler.run_once`: each due cadence creates an ordinary
**episodic intent** targeted at the cadence's node, tagged ``cadence_id`` — from there it is
indistinguishable from operator work (same meters, gates, notifications). Misfire policy: an
occurrence is *consumed* when it comes due, whether or not it fires — so occurrences missed
while the previous intent is still open (or the server was down, or the team wasn't actuated)
coalesce into at most one fire, and every skip is logged.

Cron is the standard five fields ``minute hour day-of-month month day-of-week`` evaluated in
**UTC** (all engine timestamps are UTC): ``*``, lists, ranges, and steps; day-of-week 0–7 with
both 0 and 7 = Sunday; Vixie's OR rule when both day fields are restricted. Parsed with stdlib
only — a cron library is not worth a dependency for five fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from ..deps import now_iso

# ------------------------------------------------------------------- cron
_FIELD_BOUNDS: dict[str, tuple[int, int]] = {
    "minute": (0, 59), "hour": (0, 23), "dom": (1, 31), "month": (1, 12), "dow": (0, 7),
}
# A satisfiable cron fires within 8 years (worst case: Feb 29 across a century boundary is the
# unsatisfiable one we want to reject, and 2096→2104 is the widest real leap gap).
_SCAN_DAYS = 366 * 9


class CronError(ValueError):
    """The cron expression is malformed (or provably never fires)."""


@dataclass(frozen=True)
class Cron:
    minutes: frozenset[int]
    hours: frozenset[int]
    doms: frozenset[int]
    months: frozenset[int]
    dows: frozenset[int]
    # Vixie OR rule: when BOTH day fields are restricted, a day matches if EITHER does.
    dom_star: bool
    dow_star: bool


def _parse_term(term: str, lo: int, hi: int, field: str) -> set[int]:
    step = 1
    if "/" in term:
        term, step_raw = term.split("/", 1)
        if not step_raw.isdigit() or int(step_raw) < 1:
            raise CronError(f"bad step {step_raw!r} in {field}")
        step = int(step_raw)
    if term == "*":
        start, end = lo, hi
    elif "-" in term:
        a, _, b = term.partition("-")
        if not (a.isdigit() and b.isdigit()):
            raise CronError(f"bad range {term!r} in {field}")
        start, end = int(a), int(b)
        if start > end:
            raise CronError(f"inverted range {term!r} in {field}")
    elif term.isdigit():
        # Vixie: a bare value with a step ("3/2") means "from 3 to the top, by 2".
        start = int(term)
        end = hi if step > 1 else start
    else:
        raise CronError(f"bad value {term!r} in {field}")
    if start < lo or end > hi:
        raise CronError(f"{term!r} out of range {lo}-{hi} in {field}")
    return set(range(start, end + 1, step))


def parse_cron(expr: str) -> Cron:
    parts = expr.split()
    if len(parts) != 5:
        raise CronError(
            "cron needs 5 fields (minute hour day-of-month month day-of-week), "
            f"got {len(parts)}"
        )
    fields: dict[str, set[int]] = {}
    for (name, (lo, hi)), part in zip(_FIELD_BOUNDS.items(), parts, strict=True):
        vals: set[int] = set()
        for term in part.split(","):
            vals |= _parse_term(term, lo, hi, name)
        fields[name] = vals
    dows = {d % 7 for d in fields["dow"]}  # 7 is Sunday too
    return Cron(
        minutes=frozenset(fields["minute"]), hours=frozenset(fields["hour"]),
        doms=frozenset(fields["dom"]), months=frozenset(fields["month"]),
        dows=frozenset(dows), dom_star=parts[2] == "*", dow_star=parts[4] == "*",
    )


def _day_matches(cron: Cron, d: date) -> bool:
    if d.month not in cron.months:
        return False
    dom_ok = d.day in cron.doms
    dow_ok = d.isoweekday() % 7 in cron.dows  # Monday=1 → 0=Sunday..6=Saturday
    if cron.dom_star and cron.dow_star:
        return True
    if cron.dom_star:
        return dow_ok
    if cron.dow_star:
        return dom_ok
    return dom_ok or dow_ok


def next_fire(cron: Cron, after: datetime) -> datetime | None:
    """The first matching minute strictly after ``after`` (UTC, minute resolution), or None if
    the expression never fires within the scan horizon (e.g. ``0 0 31 2 *``)."""
    t = after.astimezone(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)
    first_day = t.date()
    day = first_day
    for _ in range(_SCAN_DAYS):
        if _day_matches(cron, day):
            start_h, start_m = (t.hour, t.minute) if day == first_day else (0, 0)
            for h in sorted(cron.hours):
                if h < start_h:
                    continue
                for m in sorted(cron.minutes):
                    if h == start_h and m < start_m:
                        continue
                    return datetime(day.year, day.month, day.day, h, m, tzinfo=UTC)
        day += timedelta(days=1)
    return None


def validate_cron(expr: str) -> Cron:
    """Parse + prove satisfiable — the API-side check (routes reject with BAD_CRON)."""
    cron = parse_cron(expr)
    if next_fire(cron, datetime.now(UTC)) is None:
        raise CronError(f"{expr!r} never fires")
    return cron


# The governor's refusal reasons → the `cadence.skipped` vocabulary the activity feed
# speaks (engine.md §4): money, operator, or provider — the admission detail rides along.
_SKIP_REASONS = {
    "org-budget": "budget",
    "paused": "paused",
    "drain": "drain",
    "window-exhausted": "capacity",
    "park": "capacity",
}


# -------------------------------------------------------------- scheduler
class CadenceScheduler:
    """Fires due cadences. Stateless between passes (engine.md §8): work truth is the
    ``work_cadence`` row's ``last_fired_at`` — a control-plane restart just resumes the loop."""

    def __init__(self, store, engine, actuator, *, activity=None, scheduler=None):
        self.store = store
        self.engine = engine
        self.actuator = actuator
        self.activity = activity
        # The portfolio governor (04 §9.4, C7): standing intents consult it before they
        # submit. None = ungoverned (bare test stacks); the deps wiring always passes it.
        self.scheduler = scheduler

    def run_once(self, now: datetime | None = None):
        """One scheduler pass: fire (or consume-and-skip) every enabled cadence whose next
        occurrence after its anchor has come due. Returns the intents fired this pass."""
        from .engine import WorkError

        now = now or datetime.fromisoformat(now_iso())
        fired = []
        for c in self.store.list_cadences(enabled_only=True):
            try:
                cron = parse_cron(c.cron)
            except CronError:
                continue  # a hand-edited bad row must not kill the pass; it just never fires
            anchor = datetime.fromisoformat(c.lastFiredAt or c.createdAt)
            due = next_fire(cron, anchor)
            if due is None or due > now:
                continue
            # Consume the occurrence up front: whatever happens below, this one is spent.
            # Occurrences missed in bulk (downtime) coalesce into this single pass.
            self.store.mark_cadence_fired(c.id, now.isoformat().replace("+00:00", "Z"))
            current = self.actuator.get_current(c.teamId)
            if current is None or current.state not in ("live", "degraded"):
                self._log("cadence.skipped", c, {"reason": "not-actuated"})
                continue
            open_prev = self.store.open_intent_for_cadence(c.id)
            if open_prev is not None:
                # The misfire policy (engine.md §4): the previous occurrence is still open.
                self._log("cadence.skipped", c,
                          {"reason": "previous-open", "intentId": open_prev.id})
                continue
            fired_payload: dict = {}
            if self.scheduler is not None:
                # 04 §9.4 (C7): the governor's third boundary for standing intents — the
                # org ceiling, a paused/drained team, or an exhausted window with no rung
                # that admits. Skip-with-note; the occurrence stays consumed (coalesces).
                try:
                    node_id = self.engine._node(self.engine._org(c.teamId), c.nodeId).id
                except WorkError as exc:
                    self._log("cadence.skipped", c, {"reason": "error", "detail": str(exc)})
                    continue
                admission = self.scheduler.admit_cadence(c.teamId, node_id)
                if not admission.admit:
                    detail = {k: v for k, v in admission.payload.items() if k != "reason"}
                    self._log("cadence.skipped", c, {
                        **detail, "reason": _SKIP_REASONS.get(admission.reason, "capacity"),
                        "admission": admission.reason,
                    })
                    continue
                if admission.reason == "org-budget-approaching":
                    fired_payload["budgetWarning"] = admission.payload
            try:
                res = self.engine.submit_intent(
                    c.teamId, current.id, c.intentText, target_node=c.nodeId,
                    created_by="cadence", cadence_id=c.id,
                )
            except WorkError as exc:
                self._log("cadence.skipped", c, {"reason": "error", "detail": str(exc)})
                continue
            self.store.notify(
                c.teamId, "info", "cadence-fired", f"Cadence '{c.name}' fired",
                subject_ids=[c.id, res.intent.id], dedupe_key=res.intent.id,
            )
            self._log("cadence.fired", c, {"intentId": res.intent.id, **fired_payload})
            fired.append(res.intent)
        return fired

    def _log(self, action: str, cadence, payload: dict) -> None:
        if self.activity is not None:
            self.activity.log("system", action, team_id=cadence.teamId,
                              subject_ids=[cadence.id], payload=payload)
