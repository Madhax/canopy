"""GateService — open/resolve mechanics and the mechanical dependency sweep (engine.md §3).

All suspension is a Gate (invariant 8). This module owns the row mechanics — idempotent open,
state suspension/restore, and the two-hook dependency sweep — while the :class:`ExecutionEngine`
owns kind-specific *consequences* (funding a batch, cancelling drafts, rework funding). The split
keeps money and judgment out of the gate plumbing.

Dependency gates carry their watched edges in the payload::

    {"edges": [{"upstreamId": "as_x", "resolveOn": "delivered"|"accepted",
                "resolved": false, "refs": []}],
     "priorState": "briefed"}          # absent when the gate was opened without suspension

The **manager-await** gate (engine.md §2 11a) is the same kind with ``"await": true``: it watches
the manager's child set and resolves whenever ANY watched child reaches ``delivering`` or a
terminal state — the resume payload carries everything pending at that moment plus the
outstanding remainder. ``finish_turn`` re-arms it while children remain.
"""

from __future__ import annotations

import hashlib
import json

from ..activity import ActivityLog
from .models import ASSIGNMENT_TERMINAL_STATES, Assignment, Gate
from .store import WorkStore


def _reason_hash(kind: str, reason: str) -> str:
    return hashlib.sha256(f"{kind}|{reason}".encode()).hexdigest()[:16]


class GateService:
    def __init__(self, store: WorkStore, *, activity: ActivityLog | None = None):
        self.store = store
        self.activity = activity
        # Set by the engine: called with the assignment after a resolution restores it —
        # the wake-up ride on the delivery bus (best-effort; runtimes also poll).
        self.on_resume = None

    # ----------------------------------------------------------------- open
    def open(
        self, assignment: Assignment, kind: str, *, opened_by: str, owner: str, reason: str,
        payload: dict | None = None, suspend: bool = True,
    ) -> Gate:
        """Open a gate on the assignment. ``suspend=True`` moves it to ``gated`` and snapshots the
        prior state for resume; ``suspend=False`` records a mechanically-resolvable gate without
        touching the assignment (used for dependency tracking on ``proposed`` drafts, which are
        not live work yet). Idempotent per (assignment, kind, reason-hash)."""
        body = dict(payload or {})
        if suspend and assignment.state != "gated":
            body["priorState"] = assignment.state
        gate = self.store.create_gate(
            assignment.id, kind, opened_by=opened_by, owner=owner, reason=reason,
            reason_hash=_reason_hash(kind, reason), payload=body,
        )
        if suspend and assignment.state != "gated":
            self.store.set_assignment_state(assignment.id, "gated")
            self._log("gate.opened", assignment.teamId, [assignment.id, gate.id],
                      {"kind": kind, "reason": reason})
            # The suspend races the resolution sweep (E6): a watched upstream can deliver
            # between the gate insert above and this state flip. The sweep resolves the gate
            # but — correctly — refuses to restore an assignment that isn't gated yet, so
            # without this re-check the assignment would sleep forever on a resolved gate.
            fresh = self.store.get_gate(gate.id)
            if fresh is not None and fresh.state != "open":
                a = self.store.get_assignment(assignment.id)
                if a is not None and a.state == "gated":
                    self.store.set_assignment_state(
                        a.id, body.get("priorState") or assignment.state
                    )
                    if self.on_resume is not None:
                        self.on_resume(self.store.get_assignment(a.id))
        return gate

    # -------------------------------------------------------------- resolve
    def resolve(
        self, gate: Gate, *, resolution: dict, resolved_by: str,
        resume_state: str | None = None,
    ) -> Gate:
        """Mark the gate resolved and restore the assignment to its pre-gate state (or an explicit
        ``resume_state``). Restores only when this gate was the suspending one and the assignment
        is still ``gated`` — a resolution never tramples a state someone else moved."""
        updated = self.store.resolve_gate(
            gate.id, resolution=resolution, resolved_by=resolved_by,
        )
        prior = gate.payload.get("priorState")
        target = resume_state or prior
        a = self.store.get_assignment(gate.assignmentId)
        if target and a is not None and a.state == "gated":
            self.store.set_assignment_state(a.id, target)
            if self.on_resume is not None:
                self.on_resume(self.store.get_assignment(a.id))
        if a is not None:
            self._log("gate.resolved", a.teamId, [a.id, gate.id],
                      {"kind": gate.kind, "action": resolution.get("action", "")})
            # F9: the gate's unread notifications are now stale facts — auto-read them so the
            # inbox only rings for things that still need someone.
            self.store.mark_notifications_read_for_subject(a.teamId, gate.id)
        return updated or gate

    # ------------------------------------------------- dependency machinery
    def open_dependency(
        self, assignment: Assignment, edges: list[dict], *, opened_by: str = "system",
        suspend: bool = True,
    ) -> Gate:
        """Open the dependency gate for a delegated assignment. ``edges`` items:
        ``{"upstreamId", "resolveOn"}`` — the resolveOn snapshot happens at delegation
        (work-model.md §3)."""
        watched = [
            {"upstreamId": e["upstreamId"], "resolveOn": e.get("resolveOn", "accepted"),
             "resolved": False, "refs": []}
            for e in edges
        ]
        reason = "dependsOn:" + ",".join(sorted(e["upstreamId"] for e in watched))
        return self.open(
            assignment, "dependency", opened_by=opened_by, owner="system", reason=reason,
            payload={"edges": watched}, suspend=suspend,
        )

    def open_await(self, assignment: Assignment, child_ids: list[str]) -> Gate:
        """Arm (or re-arm) the manager-await gate over the outstanding child set. The reason keys
        on the child set, so each re-arm with a shrunken set is a fresh gate while the dedupe
        index still absorbs double-arms of the same set."""
        reason = "await:" + ",".join(sorted(child_ids))
        return self.open(
            assignment, "dependency", opened_by="system", owner="system", reason=reason,
            payload={"await": True, "children": sorted(child_ids)}, suspend=True,
        )

    def sweep(self, upstream: Assignment, threshold: str, refs: list[str]) -> list[Gate]:
        """The mechanical resolution sweep, run from its two hooks: at ``finish``
        (threshold='delivered') and at ``accept`` (threshold='accepted'). Idempotent — edges
        already marked resolved are skipped, and re-running resolves nothing twice.

        Returns the gates this sweep resolved."""
        resolved: list[Gate] = []
        for gate in self.store.list_gates(kind="dependency", state="open"):
            if gate.payload.get("await"):
                if upstream.id in gate.payload.get("children", []):
                    g = self._sweep_await(gate, upstream, refs)
                    if g is not None:
                        resolved.append(g)
                continue
            edges = gate.payload.get("edges", [])
            hit = False
            for e in edges:
                if e["upstreamId"] == upstream.id and not e["resolved"]:
                    # 'accepted' outranks 'delivered': an accepted upstream has necessarily
                    # delivered, so the accept-hook sweep also satisfies verify edges.
                    satisfied = e["resolveOn"] == threshold or (
                        threshold == "accepted" and e["resolveOn"] == "delivered"
                    )
                    if satisfied:
                        e["resolved"] = True
                        e["refs"] = refs  # pinned at the resolving version (work-model.md §3)
                        hit = True
            if not hit:
                continue
            if all(e["resolved"] for e in edges):
                downstream = self.store.get_assignment(gate.assignmentId)
                granted = [r for e in edges for r in e["refs"]]
                if granted and downstream is not None:
                    self.store.append_brief_refs(downstream.id, granted)
                self.resolve(
                    gate, resolution={"action": "auto", "refs": granted}, resolved_by="system",
                )
                resolved.append(gate)
            else:
                self.store.update_gate_payload(gate.id, gate.payload)
        return resolved

    def _sweep_await(self, gate: Gate, child: Assignment, refs: list[str]) -> Gate | None:
        """Await gates resolve on ANY watched child reaching ``delivering`` or a terminal state.
        The resume payload carries every deliverable pending review at this moment plus the
        outstanding remainder (engine.md §2 11a)."""
        if child.state != "delivering" and child.state not in ASSIGNMENT_TERMINAL_STATES:
            return None
        pending, outstanding = self.await_status(gate.payload.get("children", []))
        self.resolve(
            gate,
            resolution={"action": "auto", "pending": pending, "outstanding": outstanding},
            resolved_by="system",
        )
        return gate

    def await_status(self, child_ids: list[str]) -> tuple[list[dict], list[str]]:
        """(deliverables pending review, children still outstanding) for a watched child set."""
        pending: list[dict] = []
        outstanding: list[str] = []
        for cid in child_ids:
            c = self.store.get_assignment(cid)
            if c is None:
                continue
            if c.state == "delivering" and c.deliverableId:
                d = self.store.get_deliverable(c.deliverableId)
                if d is not None and d.accepted is None:
                    pending.append({
                        "assignmentId": c.id, "nodeId": c.nodeId, "deliverableId": d.id,
                        "kind": d.kind, "refs": d.artifactRefs, "summary": d.summary,
                    })
            if c.state not in ASSIGNMENT_TERMINAL_STATES:
                outstanding.append(c.id)
        return pending, outstanding

    # -------------------------------------------------------------- helpers
    def open_gate_for(self, assignment_id: str, kind: str | None = None) -> Gate | None:
        gates = self.store.list_gates(assignment_id=assignment_id, kind=kind, state="open")
        return gates[0] if gates else None

    def _log(self, action: str, team_id: str, subject_ids: list[str], payload: dict) -> None:
        if self.activity is not None:
            self.activity.log("system", action, team_id=team_id, subject_ids=subject_ids,
                              payload=json.loads(json.dumps(payload)))
