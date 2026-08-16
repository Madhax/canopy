"""ExecutionEngine — the orchestration that drives one assignment end to end (engine.md §2).

The engine owns work truth; runtimes only report and request. For E1 it drives the simplest path —
an operator intent to a single node, no delegation and no gates (those are E2):

    submit_intent → root assignment (briefed) + assignment-bound meter (closes D1) + brief v1
      → intake-complete → planning → declare_plan → executing
      → record_step* (metered by the gateway; the engine records the observable Step)
      → finish → deliverable (delivering)
      → accept → accepted → closed; meter closed; memory written; root → intent completed

Money stays mechanical: the meter is opened here and bound to the assignment, and the gateway
meters model calls against it (via the injected resolver in ``deps``), so the invariant-7 hard-stop
still fires before dispatch. The engine never touches the provider path itself.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel

from ..activity import ActivityLog
from ..artifacts import ArtifactMeta, ArtifactStore
from ..config import get_rework_grant_pct, get_stall_minutes, get_stall_none_steps
from ..deps import now_iso
from ..gateway.service import estimate_cost_micros
from ..ids import new_assignment_id, new_step_id
from ..ledger import BudgetLedger
from ..models import Agent, Team
from ..sqlite_store import SqliteTeamStore
from ..store import JsonFileStore
from .gates import GateService
from .models import ASSIGNMENT_TERMINAL_STATES, Assignment, Deliverable, Gate, Intent, Plan
from .store import WorkStore

OrgStore = SqliteTeamStore | JsonFileStore


class RootAssignmentResult(BaseModel):
    intent: Intent
    assignment: Assignment


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "team"


class WorkError(Exception):
    """A work-layer precondition failed (unknown node, wrong state, missing assignment)."""


class ExecutionEngine:
    def __init__(
        self, store: WorkStore, ledger: BudgetLedger, artifacts: ArtifactStore,
        team_store: OrgStore, *, activity: ActivityLog | None = None, bus=None,
        executors: dict | None = None, prices: dict | None = None,
    ):
        self.store = store
        self.ledger = ledger
        self.artifacts = artifacts
        self.teams = team_store
        self.activity = activity
        self.bus = bus  # optional: dispatch/resume wake-ups ride the A3 delivery workers
        # Governed-action executors (envelope §3.4): action name -> callable(payload) -> result.
        # The engine runs one ONLY from a resolved ApprovalGate (invariant 9).
        self.executors = executors or {}
        # Price table for the settle path (F1): CLI-reported steps estimate cost here, since
        # they never pass through the gateway. Same data the gateway holds (deps injects both).
        self.prices = prices or {}
        self.gates = GateService(store, activity=activity)
        # Gate resolutions wake the resumed node through the same delivery path as dispatch.
        self.gates.on_resume = lambda a: self._publish_wake(a, "resume")

    def _publish_wake(self, a: Assignment, kind: str, payload: dict | None = None) -> None:
        """Publish a wake envelope to the node's inbox topic (engine.md §2 step 6 — A3
        delivery). Runtimes also poll `assignment/current`, so the bus is the fast path, not
        the only path; a missing bus (unit tests) degrades to polling."""
        if self.bus is None:
            return
        from ..bus import Envelope
        from ..ids import new_message_id
        from ..router import inbox_topic

        envelope = Envelope(
            id=new_message_id(), actuationId=a.actuationId, fromNodeId="engine",
            toNodeId=a.nodeId, kind=kind, a2aPayload=payload or {}, taskRef=a.id,
            ts=now_iso(),
        )
        try:
            self.bus.publish(
                inbox_topic(a.actuationId, a.nodeId), envelope,
                idempotency_key=f"{kind}:{a.id}:{a.updatedAt}",
            )
        except Exception:  # noqa: BLE001 - a wake is best-effort; polling still succeeds
            pass

    # ----------------------------------------------------------- node resolution
    def _org(self, team_id: str) -> Team:
        return self.teams.read(team_id)

    @staticmethod
    def _node(team: Team, node_id: str | None) -> Agent:
        if node_id is None:  # default target: the team root (the agent with no manager)
            roots = [a for a in team.agents if a.managerId is None]
            if not roots:
                raise WorkError(f"team {team.id} has no root node")
            return roots[0]
        for a in team.agents:
            if a.id == node_id:
                return a
        raise WorkError(f"node {node_id!r} not found in team {team.id}")

    @staticmethod
    def _contract_for(agent: Agent) -> tuple[str, str]:
        """The node's primary deliverable contract, from its own responsibilities. Defaults to a
        generic artifact when the node declares none (the catalog role's contracts arrive in E3)."""
        for r in agent.extensions.responsibilities:
            return r.deliverable.kind, r.deliverable.type
        return "artifact", "Deliverable"

    # --------------------------------------------------------------- intent intake
    def submit_intent(
        self, team_id: str, actuation_id: str, text: str, *, target_node: str | None = None,
        kind: str = "episodic", created_by: str = "operator", allowance_override: int | None = None,
        contract_kind: str | None = None, contract_type: str | None = None,
        cadence_id: str | None = None, trigger_id: str | None = None,
        external_key: str | None = None,
    ) -> RootAssignmentResult:
        """Create a work_intent and its root Assignment, funded from the target node's salary.

        The root Assignment is born ``briefed`` with brief v1 = the intent text; its meter is
        assignment-bound (task_id = the assignment id) — the D1 close. Delivery/wake of the node is
        the runtime's concern (E1 item 4); here we establish the durable work truth.
        """
        team = self._org(team_id)
        agent = self._node(team, target_node)
        allowance = allowance_override or agent.salary.perAssignmentAllowance
        ckind = contract_kind or self._contract_for(agent)[0]
        ctype = contract_type or self._contract_for(agent)[1]
        # A cadence occurrence — or a trigger firing (standing-orgs.md §3) — is operator work
        # from here on (engine.md §4: "indistinguishable from operator work") — gates and
        # reviews route to the operator; provenance rides created_by + cadence_id/trigger_id.
        issuer = "operator" if created_by in ("cadence", "trigger") else created_by

        intent = self.store.create_intent(
            team_id, actuation_id, agent.id, text, kind=kind, created_by=created_by,
            cadence_id=cadence_id, trigger_id=trigger_id, external_key=external_key,
        )
        # Pre-mint the assignment id so the meter is bound to it in both directions.
        aid = new_assignment_id()
        meter = self.ledger.open_meter(
            actuation_id, agent.id, allowance,
            warn_threshold_pct=agent.salary.warnThresholdPct, hard_stop=agent.salary.hardStop,
            task_id=aid,
        )
        assignment = self.store.create_assignment(
            assignment_id=aid, team_id=team_id, actuation_id=actuation_id, intent_id=intent.id,
            node_id=agent.id, issued_by=issuer, contract_kind=ckind, contract_type=ctype,
            meter_id=meter.id, state="briefed",
        )
        self.store.add_brief(aid, text, revised_by=issuer)
        self.store.set_intent_root(intent.id, aid)
        self._log("intent.submitted", team_id, [intent.id, aid, agent.id],
                  {"actuationId": actuation_id, "meterId": meter.id})
        return RootAssignmentResult(intent=self.store.get_intent(intent.id), assignment=assignment)

    # ------------------------------------------------------------------ delegation
    @staticmethod
    def _reports_of(team: Team, node_id: str) -> list[Agent]:
        return [a for a in team.agents if a.managerId == node_id]

    @staticmethod
    def _dep_resolve_on(team: Team, from_node: str, to_node: str) -> str:
        """The formation-declared resolution policy for the (dependent → upstream) edge; consume
        (``accepted``) when the chart declares no edge (work-model.md §3)."""
        for d in team.dependencies:
            if d.from_ == from_node and d.to == to_node:
                return d.resolveOn
        return "accepted"

    @staticmethod
    def _checkpointed(assignment: Assignment) -> bool:
        """Does the X3 plan-review checkpoint govern this assignment's fan-out? Default policy:
        root assignments (operator-issued), per manager-responsibilities X3 / engine.md §2."""
        return assignment.parentId is None

    def delegate(
        self, caller_assignment_id: str, report_node_id: str, brief: str, *,
        refs: list[str] | None = None, contract_kind: str | None = None,
        contract_type: str | None = None, depends_on: list[dict] | None = None,
    ) -> Assignment:
        """Create a child assignment on a direct report (engine.md §2 steps 1–6).

        Checkpointed callers get the STAGED branch: the child is a ``proposed`` draft — no meter,
        nothing published — until the plan-review approval dispatches the batch. Direct callers
        get fund-and-dispatch immediately. ``depends_on`` items: ``{"assignmentId", "resolveOn"?}``
        — sibling assignment ids; resolveOn defaults to the chart's edge policy.
        """
        caller = self._require(caller_assignment_id)
        if caller.state != "executing":
            raise WorkError(f"delegate invalid from state {caller.state!r}")
        team = self._org(caller.teamId)
        report = next(
            (a for a in self._reports_of(team, caller.nodeId) if a.id == report_node_id), None,
        )
        if report is None:  # invariant 4: delegation only travels manager → direct report
            raise WorkError(f"node {report_node_id!r} is not a report of {caller.nodeId!r}")

        edges: list[dict] = []
        for dep in depends_on or []:
            up = self._require(dep["assignmentId"])
            if up.parentId != caller.id:
                raise WorkError(f"dependsOn target {up.id!r} is not a sibling assignment")
            edges.append({
                "upstreamId": up.id,
                "resolveOn": dep.get("resolveOn")
                or self._dep_resolve_on(team, report.id, up.nodeId),
            })

        ckind = contract_kind or self._contract_for(report)[0]
        ctype = contract_type or self._contract_for(report)[1]
        staged = self._checkpointed(caller)
        aid = new_assignment_id()

        if staged:
            self.store.create_assignment(
                assignment_id=aid, team_id=caller.teamId, actuation_id=caller.actuationId,
                intent_id=caller.intentId, parent_id=caller.id, node_id=report.id,
                issued_by=caller.nodeId, contract_kind=ckind, contract_type=ctype,
                meter_id=None, state="proposed",
            )
        else:
            meter = self.ledger.open_meter(
                caller.actuationId, report.id, report.salary.perAssignmentAllowance,
                warn_threshold_pct=report.salary.warnThresholdPct,
                hard_stop=report.salary.hardStop, task_id=aid,
            )
            self.store.create_assignment(
                assignment_id=aid, team_id=caller.teamId, actuation_id=caller.actuationId,
                intent_id=caller.intentId, parent_id=caller.id, node_id=report.id,
                issued_by=caller.nodeId, contract_kind=ckind, contract_type=ctype,
                meter_id=meter.id, state="briefed",
            )
        self.store.add_brief(aid, brief, artifact_refs=refs, revised_by=caller.nodeId)
        if edges:
            # Dependency tracking starts now for both branches; only live (dispatched) children
            # are actually suspended — a proposed draft is not live work yet.
            self.gates.open_dependency(
                self._require(aid), edges, suspend=not staged,
            )
        child = self._require(aid)
        if child.state == "briefed":  # direct dispatch: publish the delivery wake (A3)
            self._publish_wake(child, "assignment")
        self._log("assignment.delegated", caller.teamId, [caller.id, aid, report.id],
                  {"staged": staged, "dependsOn": [e["upstreamId"] for e in edges]})
        return child

    def finish_turn(self, caller_assignment_id: str) -> Gate | None:
        """The manager's turn boundary after a fan-out (engine.md §2 9a / 11a).

        Proposed batch pending → open the plan-review ApprovalGate with the batch as payload.
        Otherwise, children outstanding → arm (or re-arm) the await gate; children already
        delivered sweep it immediately, so a wake is never missed. No children → no-op."""
        caller = self._require(caller_assignment_id)
        if caller.state != "executing":
            raise WorkError(f"finish-turn invalid from state {caller.state!r}")

        proposed = self.store.list_children(caller.id, state="proposed")
        if proposed:
            owner = "operator" if caller.issuedBy == "operator" else caller.issuedBy
            batch = [self._draft_summary(c) for c in proposed]
            gate = self.gates.open(
                caller, "approval", opened_by="system", owner=owner,
                reason="plan-review:" + ",".join(sorted(c.id for c in proposed)),
                payload={"batch": batch},
            )
            self._log("gate.plan-review", caller.teamId, [caller.id, gate.id],
                      {"batch": [c.id for c in proposed]})
            self.store.notify(
                caller.teamId, "attention", "plan-review-waiting",
                f"{caller.nodeId}'s fan-out ({len(proposed)} delegations) awaits review",
                subject_ids=[caller.id, gate.id], dedupe_key=gate.id,
            )
            return gate

        outstanding = [
            c.id for c in self.store.list_children(caller.id)
            if c.state not in ASSIGNMENT_TERMINAL_STATES
        ]
        if not outstanding:
            return None
        gate = self.gates.open_await(caller, outstanding)
        # A child may have delivered while the manager was reviewing — sweep immediately.
        pending, _ = self.gates.await_status(outstanding)
        if pending:
            delivered = self._require(pending[0]["assignmentId"])
            self.gates.sweep(delivered, "delivered", pending[0]["refs"])
        return self.store.get_gate(gate.id)

    def _draft_summary(self, c: Assignment) -> dict:
        brief = self.store.get_brief(c.id)
        team = self._org(c.teamId)
        node = self._node(team, c.nodeId)
        dep_gate = self.gates.open_gate_for(c.id, "dependency")
        return {
            "assignmentId": c.id,
            "nodeId": c.nodeId,
            "brief": brief.text if brief else "",
            "refs": brief.artifactRefs if brief else [],
            "contract": {"kind": c.contractKind, "type": c.contractType},
            "dependsOn": dep_gate.payload.get("edges", []) if dep_gate else [],
            "allowance": node.salary.perAssignmentAllowance,
        }

    # ------------------------------------------------------------- gate resolution
    def resolve_gate(
        self, gate_id: str, *, action: str, resolved_by: str = "operator",
        payload: dict | None = None,
    ) -> Gate:
        """The one resolution surface (engine.md §6, ``POST /gates/{id}/resolve``). E2a implements
        the plan-review approval actions; the judgment-gate actions land in E2b."""
        gate = self.store.get_gate(gate_id)
        if gate is None:
            raise WorkError(f"no gate {gate_id!r}")
        if gate.state != "open":
            raise WorkError(f"gate {gate_id} is already {gate.state}")
        body = payload or {}

        if gate.kind == "approval" and gate.payload.get("governedAction"):
            return self._resolve_governed_action(gate, action=action, resolved_by=resolved_by,
                                                 body=body)

        if gate.kind == "approval" and action == "edit-draft":
            # Amend one draft brief pre-dispatch; the gate stays open for the actual verdict.
            child = self._require(body["assignmentId"])
            if child.state != "proposed":
                raise WorkError(f"cannot edit brief of state {child.state!r}")
            self.store.amend_draft_brief(child.id, body["brief"], artifact_refs=body.get("refs"))
            batch = [s for s in gate.payload.get("batch", [])]
            for s in batch:
                if s["assignmentId"] == child.id:
                    s["brief"] = body["brief"]
                    if body.get("refs") is not None:
                        s["refs"] = body["refs"]
            self.store.update_gate_payload(gate.id, {**gate.payload, "batch": batch})
            return self.store.get_gate(gate.id)  # type: ignore[return-value]

        if gate.kind == "approval" and action == "approve":
            manager = self._require(gate.assignmentId)
            dispatched = []
            for summary in gate.payload.get("batch", []):
                child = self._require(summary["assignmentId"])
                if child.state != "proposed":
                    continue  # cancelled or already handled — approval is idempotent per child
                allowance = (body.get("allowances") or {}).get(child.id)
                self._dispatch_child(child, allowance_override=allowance)
                dispatched.append(child.id)
            self.gates.resolve(
                gate, resolution={"action": "approve", "dispatched": dispatched},
                resolved_by=resolved_by,
                # The manager's suspension continues directly as its await gate — no wasted wake.
                resume_state="executing",
            )
            outstanding = [
                c.id for c in self.store.list_children(manager.id)
                if c.state not in ASSIGNMENT_TERMINAL_STATES
            ]
            if outstanding:
                self.gates.open_await(self._require(manager.id), outstanding)
            self._log("gate.batch-approved", manager.teamId, [manager.id, gate.id],
                      {"dispatched": dispatched})
            return self.store.get_gate(gate.id)  # type: ignore[return-value]

        if gate.kind == "approval" and action == "deny":
            # Denial is a prohibition: drafts cancelled, the manager re-plans (engine.md §2 9a).
            manager = self._require(gate.assignmentId)
            cancelled = []
            for summary in gate.payload.get("batch", []):
                child = self._require(summary["assignmentId"])
                if child.state == "proposed":
                    self.store.set_assignment_state(child.id, "cancelled")
                    cancelled.append(child.id)
            self.gates.resolve(
                gate, resolution={"action": "deny", "note": body.get("note", ""),
                                  "cancelled": cancelled},
                resolved_by=resolved_by,
            )
            self._log("gate.batch-denied", manager.teamId, [manager.id, gate.id],
                      {"cancelled": cancelled})
            return self.store.get_gate(gate.id)  # type: ignore[return-value]

        if gate.kind in ("clarification", "escalation", "intervention"):
            return self._resolve_judgment_gate(gate, action=action, resolved_by=resolved_by,
                                               body=body)

        raise WorkError(f"unsupported resolution {action!r} for {gate.kind!r} gate")

    def open_governed_action(
        self, assignment_id: str, action_name: str, payload: dict, *, owner: str = "operator",
    ) -> Gate:
        """An agent reached a governed action: suspend on an ApprovalGate carrying the action
        (work-model.md §3 approval row). Approval executes it; denial is a prohibition."""
        a = self._require(assignment_id)
        gate = self.gates.open(
            a, "approval", opened_by=a.nodeId, owner=owner,
            reason=f"governed:{action_name}:{a.id}",
            payload={"governedAction": action_name, **payload},
        )
        self._notify_gate_waiting(a, gate)
        return gate

    def _resolve_governed_action(
        self, gate: Gate, *, action: str, resolved_by: str, body: dict,
    ) -> Gate:
        """Consented, then evidenced (invariant 9): approval runs the registered executor and
        the result — the ActionAttestation's substance — is recorded on the gate resolution and
        the activity log, linked to the gate. Denial is a prohibition: the agent resumes and
        must re-plan around it, never treat it as a rework request."""
        a = self._require(gate.assignmentId)
        name = gate.payload["governedAction"]
        if action == "deny":
            self.gates.resolve(
                gate, resolution={"action": "deny", "note": body.get("note", "")},
                resolved_by=resolved_by,
            )
            return self.store.get_gate(gate.id)  # type: ignore[return-value]
        if action != "approve":
            raise WorkError(f"unsupported resolution {action!r} for a governed action")
        executor = self.executors.get(name)
        if executor is None:
            raise WorkError(f"no executor registered for governed action {name!r}")
        result = executor(dict(gate.payload))
        self.gates.resolve(
            gate,
            resolution={"action": "approve", "executed": name, "result": result,
                        "attestation": {"claim": f"{name} executed under gate {gate.id}",
                                        "gateId": gate.id, "approvedBy": resolved_by}},
            resolved_by=resolved_by,
        )
        self._log("governed.executed", a.teamId, [a.id, gate.id],
                  {"action": name, "result": result})
        return self.store.get_gate(gate.id)  # type: ignore[return-value]

    def _resolve_judgment_gate(
        self, gate: Gate, *, action: str, resolved_by: str, body: dict,
    ) -> Gate:
        """Resolutions for the judgment gates (work-model.md §3 table). The resolution payload is
        recorded on the gate; the runtime renders it as the next session input on resume."""
        a = self._require(gate.assignmentId)
        resolution: dict = {"action": action, "note": body.get("note", "")}

        if action == "resume" and gate.kind == "intervention":
            self.gates.resolve(gate, resolution=resolution, resolved_by=resolved_by)

        elif action == "revise-brief" and gate.kind in ("clarification", "intervention"):
            # Clarification: the manager answers with a revised brief; the node re-intakes.
            # Intervention redirect: same mechanics, back through planning.
            if "brief" not in body:
                raise WorkError("revise-brief needs a brief")
            self.store.add_brief(a.id, body["brief"], artifact_refs=body.get("refs"),
                                 revised_by=resolved_by)
            resolution["briefVersion"] = self.store.get_brief(a.id).version
            resume = "briefed" if gate.kind == "clarification" else "planning"
            self.gates.resolve(gate, resolution=resolution, resolved_by=resolved_by,
                               resume_state=resume)

        elif action == "answer" and gate.kind == "escalation":
            resolution["answer"] = body.get("answer", body.get("note", ""))
            refs = body.get("refs") or []
            if refs:  # granted refs travel with the answer, as a system brief revision
                self.store.append_brief_refs(a.id, refs)
                resolution["refs"] = refs
            self.gates.resolve(gate, resolution=resolution, resolved_by=resolved_by)

        elif action == "top-up" and gate.kind == "intervention":
            amount = int(body.get("amount", 0))
            if amount <= 0:
                raise WorkError("top-up needs a positive amount")
            if a.meterId is None:
                raise WorkError("assignment has no meter to top up")
            self.ledger.raise_meter(a.meterId, amount)
            resolution["amount"] = amount
            self.gates.resolve(gate, resolution=resolution, resolved_by=resolved_by)
            self._log("meter.topped-up", a.teamId, [a.id, a.meterId], {"amount": amount})

        elif action == "reassign" and gate.kind == "intervention":
            to_node = body.get("toNodeId")
            if not to_node:
                raise WorkError("reassign needs toNodeId")
            replacement = self._reassign(a, to_node, by=resolved_by)
            resolution["reassignedTo"] = replacement.id
            self.gates.resolve(gate, resolution=resolution, resolved_by=resolved_by,
                               resume_state="cancelled")

        elif action == "cancel":
            self.gates.resolve(gate, resolution=resolution, resolved_by=resolved_by,
                               resume_state=a.state if a.state != "gated" else None)
            self.cancel_assignment(a.id, by=resolved_by, reason=body.get("note", ""))

        else:
            raise WorkError(f"unsupported resolution {action!r} for {gate.kind!r} gate")

        return self.store.get_gate(gate.id)  # type: ignore[return-value]

    # ---------------------------------------------------------------- judgment gates
    def open_clarification(self, assignment_id: str, question: str) -> Gate:
        """The assigned agent's intake feasibility check failed (work-model.md §3): suspend on a
        clarification gate owned by the issuing manager (operator for the root)."""
        a = self._require(assignment_id)
        if a.state not in ("briefed", "intake", "planning"):
            raise WorkError(f"clarification invalid from state {a.state!r}")
        gate = self.gates.open(
            a, "clarification", opened_by=a.nodeId, owner=a.issuedBy,
            reason=f"clarification:{question[:80]}", payload={"question": question},
        )
        self._notify_gate_waiting(a, gate)
        return gate

    def open_escalation(
        self, assignment_id: str, question: str, *, refs: list[str] | None = None,
    ) -> Gate:
        """The agent asks above its pay grade mid-execution; the answer is injected on resume."""
        a = self._require(assignment_id)
        if a.state != "executing":
            raise WorkError(f"escalation invalid from state {a.state!r}")
        gate = self.gates.open(
            a, "escalation", opened_by=a.nodeId, owner=a.issuedBy,
            reason=f"escalation:{question[:80]}",
            payload={"question": question, "refs": refs or []},
        )
        self._notify_gate_waiting(a, gate)
        return gate

    def intervene(self, assignment_id: str, note: str, *, by: str = "operator") -> Gate:
        """X1: an authority's judgment suspends the assignment (halt lands at the next turn
        boundary — the same place the meter check sits)."""
        a = self._require(assignment_id)
        if a.state not in ("briefed", "intake", "planning", "executing", "delivering"):
            raise WorkError(f"intervene invalid from state {a.state!r}")
        gate = self.gates.open(
            a, "intervention", opened_by=by, owner="operator",
            reason=f"intervention:{by}:{note[:80]}", payload={"note": note},
        )
        self._notify_gate_waiting(a, gate)
        return gate

    # ------------------------------------------------------- triggers (work-model §6)
    def check_budget_triggers(self, assignment_id: str) -> None:
        """Evaluated on every step report: budget warn (notification, once) and hard-stop
        (InterventionGate, `opened_by='trigger:hard-stop'`)."""
        a = self.store.get_assignment(assignment_id)
        if a is None or a.meterId is None:
            return
        meter = self.ledger.get_meter(a.meterId)
        if meter is None:
            return
        if meter.warned and meter.state != "exhausted":
            self.store.notify(
                a.teamId, "warning", "budget-warn",
                f"{a.nodeId} crossed {int(meter.warnThresholdPct)}% of its allowance",
                subject_ids=[a.id, meter.id], dedupe_key=f"{a.id}:{meter.allowance}",
            )
        if meter.state == "exhausted" and a.state in ("executing", "delivering"):
            gate = self.gates.open(
                a, "intervention", opened_by="trigger:hard-stop", owner="operator",
                # The allowance in the reason means a post-top-up re-exhaustion opens a NEW gate.
                reason=f"hard-stop:{meter.id}:{meter.allowance}",
                payload={"meterId": meter.id, "spent": meter.spent,
                         "allowance": meter.allowance},
            )
            self.store.notify(
                a.teamId, "attention", "hard-stop",
                f"{a.nodeId} exhausted its meter ({meter.spent}/{meter.allowance} tokens)",
                subject_ids=[a.id, gate.id], dedupe_key=f"{a.id}:{meter.allowance}",
            )

    #: F14: with liveness reporting, a no-delta run only counts as spinning once the session
    #: has also been silent this long — a manager mid-review settles nones while thinking.
    NO_DELTA_ACTIVITY_GRACE_SECONDS = 120

    def sweep_triggers(self) -> list[Gate]:
        """The 30 s sweep (engine.md §1): stall detection over every ``executing`` assignment.

        Reworked per the live run's findings (phase3-debts.md F3/F11/F14):
        - liveness anchors on the runtime's ``last_activity_at`` where reported — any stream
          event is proof of life, so a long-thinking session is never "quiet";
        - an ``erroring`` session is not a stall: it surfaces as a ``provider-limit`` /
          ``session-error`` notification (the operator sees the cause, e.g. "session limit ·
          resets 12:50am"), with NO intervention gate — the adapter backs off and resumes;
        - the K-consecutive-no-delta trigger only fires once the session has ALSO been quiet
          past a grace window, so a manager's wake-turn (status polls + thinking) stops
          tripping it mid-turn.
        A non-reporting runtime (loop) has no health columns and keeps the original step
        inference unchanged. Idempotent via the gate dedupe (keyed on the newest step id)."""
        opened: list[Gate] = []
        stall_after = get_stall_minutes() * 60
        k = get_stall_none_steps()
        now = datetime.fromisoformat(now_iso())
        for a in self.store.list_assignments(state="executing"):
            steps = self.store.list_steps(a.id)
            last_id = steps[-1].id if steps else "none"

            # F11: a dead-with-error session is a provider problem, not a stall.
            if a.sessionHealth == "erroring":
                detail = a.sessionHealthDetail or "session error"
                kind = ("provider-limit"
                        if re.search(r"limit|resets|overloaded|quota", detail, re.I)
                        else "session-error")
                self.store.notify(
                    a.teamId, "warning", kind, f"{a.nodeId} session failing: {detail}",
                    subject_ids=[a.id], dedupe_key=f"{kind}:{a.id}:{detail[:80]}",
                )
                continue

            anchors = [steps[-1].createdAt if steps else a.updatedAt]
            if a.lastActivityAt:
                anchors.append(a.lastActivityAt)
            activity_age = (now - datetime.fromisoformat(max(anchors))).total_seconds()

            reason = None
            if activity_age >= stall_after:
                reason = f"stall:quiet:{a.id}:{last_id}"
                detail = f"no step for {int(activity_age // 60)} min"
            elif (
                len(steps) >= k
                and all(s.deltaKind == "none" for s in steps[-k:])
                and (a.lastActivityAt is None
                     or activity_age >= self.NO_DELTA_ACTIVITY_GRACE_SECONDS)
            ):
                reason = f"stall:no-delta:{a.id}:{last_id}"
                detail = f"{k} consecutive steps with no delta"
            if reason is None:
                continue
            gate = self.gates.open(
                a, "intervention", opened_by="trigger:stall", owner="operator",
                reason=reason, payload={"detail": detail},
            )
            if self.store.notify(
                a.teamId, "warning", "stall", f"{a.nodeId} stalled: {detail}",
                subject_ids=[a.id, gate.id], dedupe_key=reason,
            ) is not None:
                opened.append(gate)
        return opened

    # ------------------------------------------------- reassign / cancel / priority
    def _reassign(self, a: Assignment, to_node_id: str, *, by: str) -> Assignment:
        """R2: cancel the assignment and re-issue it to another of the issuer's reports, carrying
        ``reassigned_from`` and the meter's remaining balance."""
        team = self._org(a.teamId)
        if a.issuedBy != "operator":
            reports = {r.id for r in self._reports_of(team, a.issuedBy)}
            if to_node_id not in reports:
                raise WorkError(f"node {to_node_id!r} is not a report of {a.issuedBy!r}")
        target = self._node(team, to_node_id)
        remaining = 0
        if a.meterId is not None:
            meter = self.ledger.get_meter(a.meterId)
            if meter is not None:
                remaining = max(0, meter.allowance - meter.spent - meter.reserved)
                self.ledger.close_meter(meter.id)
        brief = self.store.get_brief(a.id)
        self.store.set_assignment_state(a.id, "cancelled")

        aid = new_assignment_id()
        new_meter = self.ledger.open_meter(
            a.actuationId, to_node_id, remaining or target.salary.perAssignmentAllowance,
            warn_threshold_pct=target.salary.warnThresholdPct,
            hard_stop=target.salary.hardStop, task_id=aid,
        )
        replacement = self.store.create_assignment(
            assignment_id=aid, team_id=a.teamId, actuation_id=a.actuationId,
            intent_id=a.intentId, parent_id=a.parentId, node_id=to_node_id,
            issued_by=a.issuedBy, contract_kind=a.contractKind, contract_type=a.contractType,
            meter_id=new_meter.id, state="briefed", reassigned_from=a.id,
        )
        self.store.add_brief(
            aid, brief.text if brief else "", artifact_refs=brief.artifactRefs if brief else [],
            revised_by=by,
        )
        self._log("assignment.reassigned", a.teamId, [a.id, aid, to_node_id],
                  {"remaining": remaining})
        return replacement

    def cancel_assignment(self, assignment_id: str, *, by: str = "operator",
                          reason: str = "") -> Assignment:
        """Cancel an assignment and cascade: children cancelled depth-first, meters closed, open
        gates expired — no orphans (testing.md §4 vector). A cancelled root cancels its intent."""
        a = self._require(assignment_id)
        if a.state in ASSIGNMENT_TERMINAL_STATES:
            return a
        for child in self.store.list_children(a.id):
            if child.state not in ASSIGNMENT_TERMINAL_STATES:
                self.cancel_assignment(child.id, by=by, reason=f"parent cancelled: {reason}")
        for gate in self.store.list_gates(assignment_id=a.id, state="open"):
            self.store.resolve_gate(
                gate.id, resolution={"action": "expired", "note": "assignment cancelled"},
                resolved_by=by, state="expired",
            )
        if a.meterId is not None:
            self.ledger.close_meter(a.meterId)
        self.store.set_assignment_state(a.id, "cancelled")
        if a.parentId is None:
            self.store.close_intent(a.intentId, "cancelled")
        self._log("assignment.cancelled", a.teamId, [a.id], {"by": by, "reason": reason})
        return self._require(assignment_id)

    def set_priority(self, assignment_id: str, priority: int) -> Assignment:
        """R3: manager- or operator-set priority (higher first; FIFO within equal)."""
        self._require(assignment_id)
        self.store.set_assignment_priority(assignment_id, priority)
        return self._require(assignment_id)

    def _notify_gate_waiting(self, a: Assignment, gate: Gate) -> None:
        severity = "attention" if gate.owner == "operator" else "warning"
        self.store.notify(
            a.teamId, severity, "gate-waiting",
            f"{gate.kind} gate on {a.nodeId} awaits {gate.owner}",
            subject_ids=[a.id, gate.id], dedupe_key=gate.id,
        )

    def _dispatch_child(self, child: Assignment, *, allowance_override: int | None = None) -> None:
        """Fund and dispatch one approved draft: ``proposed → briefed`` with a fresh meter; a
        child whose dependency gate still has unresolved edges goes straight to ``gated``
        (engine.md §2 step 5 — genuinely idle, consuming nothing)."""
        team = self._org(child.teamId)
        node = self._node(team, child.nodeId)
        allowance = allowance_override or node.salary.perAssignmentAllowance
        meter = self.ledger.open_meter(
            child.actuationId, child.nodeId, allowance,
            warn_threshold_pct=node.salary.warnThresholdPct, hard_stop=node.salary.hardStop,
            task_id=child.id,
        )
        self.store.set_assignment_meter(child.id, meter.id)
        self.store.set_assignment_state(child.id, "briefed")
        dep_gate = self.gates.open_gate_for(child.id, "dependency")
        if dep_gate and not dep_gate.payload.get("await"):
            edges = dep_gate.payload.get("edges", [])
            if not all(e["resolved"] for e in edges):
                # Activate the pre-recorded gate: now that the child is live, it suspends.
                self.store.update_gate_payload(
                    dep_gate.id, {**dep_gate.payload, "priorState": "briefed"},
                )
                self.store.set_assignment_state(child.id, "gated")
            else:
                granted = [r for e in edges for r in e["refs"]]
                if granted:
                    self.store.append_brief_refs(child.id, granted)
                self.gates.resolve(
                    dep_gate, resolution={"action": "auto", "refs": granted},
                    resolved_by="system",
                )
        dispatched = self._require(child.id)
        if dispatched.state == "briefed":
            self._publish_wake(dispatched, "assignment")

    # ---------------------------------------------------------------- runtime reports
    def _require(self, assignment_id: str) -> Assignment:
        a = self.store.get_assignment(assignment_id)
        if a is None:
            raise WorkError(f"no assignment {assignment_id!r}")
        return a

    def mark_intake_complete(self, assignment_id: str) -> Assignment:
        """Feasibility check passed → the node may plan (E1 has no clarification gate)."""
        a = self._require(assignment_id)
        if a.state not in ("briefed", "intake"):
            raise WorkError(f"intake-complete invalid from state {a.state!r}")
        self.store.set_assignment_state(assignment_id, "planning")
        return self._require(assignment_id)

    def declare_plan(self, assignment_id: str, stages: list[dict]) -> Plan:
        """Store the declared plan and enter execution (E1: no X3 plan-review checkpoint)."""
        a = self._require(assignment_id)
        plan = self.store.create_plan(assignment_id, stages)
        if a.state == "planning":
            self.store.set_assignment_state(assignment_id, "executing")
        return plan

    def record_step(
        self, assignment_id: str, *, input_tokens: int, output_tokens: int, duration_ms: int,
        kind: str = "production", stage_idx: int | None = None, delta_kind: str = "none",
        delta_ref: str | None = None, step_id: str | None = None,
        session_span_id: str | None = None, settle: bool = False, model: str = "claude-cli",
        cache_read_tokens: int = 0, cache_creation_tokens: int = 0,
        provider_label: str | None = None,
    ):
        """Record an observable Step.

        ``settle=False`` (the loop runtime): money was already metered by the gateway when it
        made the model call — the shared ``step_id`` ties the two rows. ``settle=True`` (the
        cli-claude adapter, cli-runtime.md §5): the session's usage is CLI-reported, so this
        report ALSO lands the SpendEvent in the ledger (``provider='claude-cli'``, step-id
        idempotent — a redelivered report never double-charges). Overshoot past the allowance is
        accepted and immediately trips the hard-stop trigger (debt E-D1: enforcement is
        per-turn, not per-call).

        Cache tokens (F1): the CLI reports the cached context window as separate usage
        components; they ride the Step and the SpendEvent and are priced cache-aware. The
        METER still charges input+output only — the meter currency stays raw uncached tokens
        until allowances are re-sized (the F1 debt row records the decision); est_cost is the
        honest number."""
        a = self._require(assignment_id)
        step = self.store.add_step(
            assignment_id, input_tokens=input_tokens, output_tokens=output_tokens,
            duration_ms=duration_ms, kind=kind, stage_idx=stage_idx, delta_kind=delta_kind,
            delta_ref=delta_ref, step_id=step_id, session_span_id=session_span_id,
            cache_read_tokens=cache_read_tokens, cache_creation_tokens=cache_creation_tokens,
        )
        if settle and a.meterId is not None:
            # The CLI reports the model it ran; price it like the gateway would (anthropic
            # rates apply to claude-cli sessions — the provider is the transport, not the
            # billing identity).
            est_cost, _known = estimate_cost_micros(
                self.prices, "anthropic", model, input_tokens, output_tokens,
                cache_read_tokens, cache_creation_tokens,
            )
            self.ledger.record(
                a.meterId, step_id=step.id, team_id=a.teamId, node_id=a.nodeId,
                actuation_id=a.actuationId,
                # C6 K10: while the extra-usage rung is engaged the caller labels
                # the spend 'claude-extra' — money, never subscription "$0" rows.
                provider=provider_label or "claude-cli", model=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_creation_tokens=cache_creation_tokens, est_cost_micros=est_cost,
                reserved=0, task_id=assignment_id,
            )
        # Trigger evaluation rides every step report (work-model.md §6): warn + hard-stop.
        # (Liveness is NOT bumped here: last_activity_at belongs to the adapter's stream
        # reports (F14) so a non-reporting runtime keeps pure step inference, and the step's
        # own timestamp already anchors the quiet check.)
        self.check_budget_triggers(assignment_id)
        return step

    def report_session_health(
        self, assignment_id: str, health: str, detail: str | None = None,
    ) -> None:
        """F14: the adapter's liveness/health report — any stream event is 'running'; a session
        that died with a provider error is 'erroring' with the error text. The stall sweep keys
        on this instead of inferring life from settled steps."""
        self._require(assignment_id)
        self.store.set_session_health(assignment_id, health, detail)

    def update_stage(self, assignment_id: str, idx: int, state: str) -> None:
        """Advance a plan stage (the runtime's ``stage-update`` report). No-op if no plan yet."""
        plan = self.store.get_plan(assignment_id)
        if plan is not None:
            self.store.set_stage_state(plan.id, idx, state)

    def put_artifact(
        self, assignment_id: str, name: str, type: str, content: bytes, *,
        filename: str | None = None,
    ) -> ArtifactMeta:
        """Store an output in the Artifact Store under the assignment's team/node (grant checks in
        E3). The returned ``ref`` is what ``finish`` carries as the deliverable."""
        a = self._require(assignment_id)
        team = self._org(a.teamId)
        return self.artifacts.put(
            a.teamId, _slugify(team.name), a.nodeId, name, type, content,
            task_id=assignment_id, filename=filename,
        )

    def finish(
        self, assignment_id: str, *, artifact_refs: list[str] | None = None, summary: str = "",
        kind: str | None = None, attestation: dict | None = None,
    ) -> Deliverable:
        """Submit the deliverable and move to ``delivering`` — awaiting the manager's acceptance."""
        a = self._require(assignment_id)
        dkind = kind or a.contractKind
        deliverable = self.store.create_deliverable(
            assignment_id, dkind, artifact_refs=artifact_refs, attestation=attestation,
            summary=summary,
        )
        self.store.set_deliverable_ref(assignment_id, deliverable.id)
        self.store.set_assignment_state(assignment_id, "delivering")
        # First dependency hook (work-model.md §3): resolve 'delivered'-threshold (verify)
        # watchers and wake any manager awaiting this child, refs pinned at the submitted version.
        self.gates.sweep(self._require(assignment_id), "delivered", deliverable.artifactRefs)
        self._log("assignment.delivering", a.teamId, [assignment_id, deliverable.id],
                  {"refs": deliverable.artifactRefs})
        return deliverable

    # ------------------------------------------------------------------ acceptance
    def accept(self, assignment_id: str, note: str | None = None) -> Assignment:
        """Accept the deliverable — the final verdict, informed by verification (amendment D-1):
        close the assignment + meter, write memory, resolve 'accepted'-threshold (consume)
        watchers, and — for a root assignment — complete its intent."""
        a = self._require(assignment_id)
        if a.deliverableId is None:
            raise WorkError(f"assignment {assignment_id} has no deliverable to accept")
        deliverable = self.store.get_deliverable(a.deliverableId)
        self.store.review_deliverable(a.deliverableId, True, note)
        self.store.set_assignment_state(assignment_id, "accepted")
        if a.meterId is not None:
            self.ledger.close_meter(a.meterId)
        self._write_memory(a, outcome="accepted")
        self.store.set_assignment_state(assignment_id, "closed")
        # Second dependency hook: 'accepted'-threshold (consume) watchers auto-resolve, and any
        # manager awaiting this child sees it reach a terminal state.
        refs = deliverable.artifactRefs if deliverable else []
        self.gates.sweep(self._require(assignment_id), "accepted", refs)
        if a.parentId is None:
            self.store.close_intent(a.intentId, "completed")
            self._log("intent.completed", a.teamId, [a.intentId, assignment_id], {})
            self.store.notify(
                a.teamId, "info", "intent-completed", "Intent completed — deliverable ready",
                subject_ids=[a.intentId, assignment_id], dedupe_key=a.intentId,
            )
        return self._require(assignment_id)

    def reject(
        self, assignment_id: str, note: str, *, revised_brief: str | None = None,
    ) -> Assignment:
        """Reject the deliverable and re-queue to ``planning`` for rework — on the *still-open*
        assignment (amendment D-1: verification precedes acceptance, so a rejection lands while
        the assignment is ``delivering``).

        Rework funding follows the brief version (work-model.md §2.2): unchanged brief → the same
        meter keeps burning (a quality failure stays the report's visible cost); revised brief →
        the meter is topped up by the configured rework grant, debited from the parent
        assignment's meter — re-scoping is the manager's failure and surfaces one level up."""
        a = self._require(assignment_id)
        if a.deliverableId is None:
            raise WorkError(f"assignment {assignment_id} has no deliverable to reject")
        self.store.review_deliverable(a.deliverableId, False, note)
        if revised_brief is not None:
            self.store.add_brief(assignment_id, revised_brief, revised_by=a.issuedBy)
            self._fund_rework(a)
        self.store.set_assignment_state(assignment_id, "rejected")
        self.store.set_assignment_state(assignment_id, "planning")
        self._log("assignment.rejected", a.teamId, [assignment_id],
                  {"note": note, "revisedBrief": revised_brief is not None})
        self.store.notify(
            a.teamId, "warning", "deliverable-rejected",
            f"{a.nodeId}'s deliverable rejected: {note[:120]}",
            subject_ids=[assignment_id], dedupe_key=f"{assignment_id}:{a.deliverableId}",
        )
        return self._require(assignment_id)

    def _fund_rework(self, a: Assignment) -> None:
        """Revised-brief rework: top the child's meter up from the parent's, as a visible
        ``transfer`` SpendEvent (provider='canopy', model='meter-transfer') so rollups show it.
        The root's parent is the intent — its "meter" is the operator's explicit top-up approval,
        so no transfer happens here (the operator raises the meter via the gate resolution)."""
        if a.parentId is None or a.meterId is None:
            return
        parent = self._require(a.parentId)
        if parent.meterId is None:
            return
        meter = self.ledger.get_meter(a.meterId)
        if meter is None:
            return
        grant = int(meter.allowance * get_rework_grant_pct() / 100)
        if grant <= 0:
            return
        # Debit the parent (reserve → record keeps every invariant + warn/hard-stop honest),
        # then raise the child. BudgetExhausted propagates: an unfundable rework surfaces up.
        reservation = self.ledger.reserve(parent.meterId, grant)
        try:
            self.ledger.record(
                parent.meterId, step_id=new_step_id(), team_id=a.teamId, node_id=parent.nodeId,
                actuation_id=a.actuationId, provider="canopy", model="meter-transfer",
                input_tokens=grant, output_tokens=0, est_cost_micros=0,
                reserved=reservation.amount, task_id=parent.id,
            )
        except Exception:
            self.ledger.release(reservation)
            raise
        self.ledger.raise_meter(a.meterId, grant)
        self._log("meter.transfer", a.teamId, [parent.id, a.id],
                  {"grant": grant, "from": parent.meterId, "to": a.meterId})

    # --------------------------------------------------------------------- helpers
    def _write_memory(self, a: Assignment, *, outcome: str) -> None:
        intent = self.store.get_intent(a.intentId)
        meter = self.ledger.get_meter(a.meterId) if a.meterId else None
        deliverable = self.store.get_deliverable(a.deliverableId) if a.deliverableId else None
        self.store.append_memory(a.teamId, a.nodeId, {
            "assignmentId": a.id,
            "intentText": intent.text if intent else "",
            "outcome": outcome,
            "summary": deliverable.summary if deliverable else "",
            "costTokens": meter.spent if meter else 0,
        })

    def _log(self, action: str, team_id: str, subject_ids: list[str], payload: dict) -> None:
        if self.activity is not None:
            self.activity.log("system", action, team_id=team_id, subject_ids=subject_ids,
                              payload=payload)
