"""Trigger scheduler (docs/design/standing-orgs.md) — "work that arrives".

The event-driven sibling of :mod:`cadence`: a 60 s lifespan loop calls
:meth:`TriggerScheduler.run_once`; each enabled trigger on a live team polls its connector
instance for new external events (v1: GitHub issues) and opens one ordinary **episodic
intent** per event. Two deliberate divergences from the cadence scheduler, both because
events are durable upstream while clock ticks are not:

- Nothing is consumed on failure or downtime: the cursor advances only on a clean pass, and
  the fire ledger (``work_trigger_fire``, written in the same transaction as the intent)
  guarantees at-most-once per event regardless of cursor state.
- A burst drains bounded: at most ``max_per_pass`` intents per trigger per pass, oldest
  first — no thundering herd of plan reviews after a backfill or an outage.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from ..github_client import GitHubError, issue_template_vars, render_template

_OVERLAP_MINUTES = 5  # re-scan window; the fire ledger absorbs the duplicates
DEFAULT_MAX_PER_PASS = 3


class TriggerScheduler:
    def __init__(self, store, engine, actuator, connectors, secret_store, github, catalog, *,
                 activity=None, max_per_pass: int = DEFAULT_MAX_PER_PASS):
        self.store = store
        self.engine = engine
        self.actuator = actuator
        self.connectors = connectors
        self.secrets = secret_store
        self.github = github
        self.catalog = catalog
        self.activity = activity
        self.max_per_pass = max_per_pass

    # ------------------------------------------------------------------ passes
    def run_once(self) -> list:
        """One pass over every enabled trigger. Per-trigger try (the E6 rule): one broken
        trigger — bad credential, deleted instance — must not starve the rest."""
        fired = []
        for t in self.store.list_triggers(enabled_only=True):
            current = self.actuator.get_current(t.teamId)
            if current is None or current.state not in ("live", "degraded"):
                continue  # events are durable — nothing is consumed while down
            try:
                fired.extend(self._poll(t, current))
            except Exception as exc:  # noqa: BLE001 - recorded, surfaced, never fatal
                self._fail(t, str(exc))
        return fired

    def check_now(self, trigger_id: str) -> dict:
        """The *check now* button: one synchronous pass for one trigger."""
        t = self.store.get_trigger(trigger_id)
        if t is None:
            return {"fired": [], "candidates": 0}
        current = self.actuator.get_current(t.teamId)
        if current is None or current.state not in ("live", "degraded"):
            return {"fired": [], "candidates": 0, "skipped": "not-actuated"}
        try:
            candidates = self._candidates(t)
            fired = self._fire(t, current, candidates)
            return {"fired": [i.id for i in fired], "candidates": len(candidates)}
        except (GitHubError, LookupError) as exc:
            self._fail(t, str(exc))
            return {"fired": [], "candidates": 0, "error": str(exc)}

    def dry_run(self, trigger_id: str) -> dict:
        """The poll without the firing: candidate list + the rendered intent for the first.
        No cursor movement, no fire rows (standing-orgs.md §4)."""
        t = self.store.get_trigger(trigger_id)
        if t is None:
            return {"candidates": []}
        issues = self._candidates(t)
        preview = None
        if issues:
            preview = render_template(t.intentTemplate, issue_template_vars(issues[0]))
        return {
            "candidates": [{"key": _key(i), "title": i.get("title", ""),
                            "url": i.get("html_url", "")} for i in issues],
            "renderedFirst": preview,
        }

    # ---------------------------------------------------------------- internals
    def _instance(self, t):
        inst = self.connectors.get(t.instanceId)
        if inst is None or inst.teamId != t.teamId:
            raise LookupError(f"connector instance {t.instanceId} is gone")
        if not inst.enabled:
            raise LookupError(f"connector instance {inst.name!r} is disabled")
        return inst

    def _candidates(self, t) -> list[dict]:
        """New matching issues, oldest-first, not yet in the fire ledger."""
        inst = self._instance(t)
        token = ""
        sid = inst.secretBindings.get("scm-token")
        if sid:
            token = self.secrets.reveal(sid) or ""
        cfg = t.config or {}
        since = (t.cursor or {}).get("since") or cfg.get("createdAfter")
        if since:
            # Overlap the window; the ledger absorbs re-scans (standing-orgs.md §3).
            dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            since = (dt - timedelta(minutes=_OVERLAP_MINUTES)).astimezone(UTC).isoformat()
        issues = self.github.list_issues(
            token, inst.config.get("owner", ""), inst.config.get("repo", ""),
            state=cfg.get("state", "open"), labels=cfg.get("labels") or None, since=since,
        )
        created_after = cfg.get("createdAfter")
        if created_after:
            issues = [i for i in issues if (i.get("created_at") or "") >= created_after]
        seen = self.store.trigger_fired_keys(t.id)
        return [i for i in issues if _key(i) not in seen]

    def _fire(self, t, current, candidates: list[dict]) -> list:
        from .engine import WorkError

        fired = []
        newest = (t.cursor or {}).get("since")
        for issue in candidates[: self.max_per_pass]:
            text = render_template(t.intentTemplate, issue_template_vars(issue))
            try:
                res = self.engine.submit_intent(
                    t.teamId, current.id, text, target_node=t.nodeId,
                    created_by="trigger", trigger_id=t.id, external_key=_key(issue),
                )
            except sqlite3.IntegrityError:
                continue  # a concurrent pass claimed this event first — exactly-once held
            except WorkError as exc:
                self._log("trigger.skipped", t, {"reason": "error", "detail": str(exc)})
                continue
            fired.append(res.intent)
            self.store.notify(
                t.teamId, "info", "trigger-fired",
                f"Trigger '{t.name}' opened intent for {_key(issue)}",
                subject_ids=[t.id, res.intent.id], dedupe_key=res.intent.id,
            )
            self._log("trigger.fired", t, {"intentId": res.intent.id, "key": _key(issue)})
        # Cursor: the newest updated_at actually seen this pass — only on success, and only
        # when the whole candidate set drained (a capped pass must re-see the remainder).
        if len(candidates) <= self.max_per_pass:
            for issue in candidates:
                ts = issue.get("updated_at") or issue.get("created_at")
                if ts and (newest is None or ts > newest):
                    newest = ts
        self.store.mark_trigger_checked(
            t.id, cursor={"since": newest} if newest else None, fired=bool(fired),
        )
        return fired

    def _poll(self, t, current) -> list:
        return self._fire(t, current, self._candidates(t))

    def _fail(self, t, detail: str) -> None:
        self.store.mark_trigger_checked(t.id, error=detail)
        # Deduped on the error string: one warning per failure streak, not one per poll.
        self.store.notify(
            t.teamId, "warning", "trigger-error",
            f"Trigger '{t.name}' failed: {detail[:200]}",
            subject_ids=[t.id], dedupe_key=f"{t.id}:{detail[:80]}",
        )
        self._log("trigger.error", t, {"detail": detail[:300]})

    def _log(self, action: str, t, payload: dict) -> None:
        if self.activity is not None:
            self.activity.log("system", action, team_id=t.teamId,
                              subject_ids=[t.id], payload=payload)


def _key(issue: dict) -> str:
    return f"issue:{issue.get('number')}"
