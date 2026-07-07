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

from pydantic import BaseModel

from ..activity import ActivityLog
from ..artifacts import ArtifactMeta, ArtifactStore
from ..ids import new_assignment_id
from ..ledger import BudgetLedger
from ..models import Agent, Organization
from ..sqlite_store import SqliteOrgStore
from ..store import JsonFileStore
from .models import Assignment, Deliverable, Intent, Plan
from .store import WorkStore

OrgStore = SqliteOrgStore | JsonFileStore


class RootAssignmentResult(BaseModel):
    intent: Intent
    assignment: Assignment


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "organization"


class WorkError(Exception):
    """A work-layer precondition failed (unknown node, wrong state, missing assignment)."""


class ExecutionEngine:
    def __init__(
        self, store: WorkStore, ledger: BudgetLedger, artifacts: ArtifactStore,
        org_store: OrgStore, *, activity: ActivityLog | None = None,
    ):
        self.store = store
        self.ledger = ledger
        self.artifacts = artifacts
        self.orgs = org_store
        self.activity = activity

    # ----------------------------------------------------------- node resolution
    def _org(self, org_id: str) -> Organization:
        return self.orgs.read(org_id)

    @staticmethod
    def _node(org: Organization, node_id: str | None) -> Agent:
        if node_id is None:  # default target: the org root (the agent with no manager)
            roots = [a for a in org.agents if a.managerId is None]
            if not roots:
                raise WorkError(f"org {org.id} has no root node")
            return roots[0]
        for a in org.agents:
            if a.id == node_id:
                return a
        raise WorkError(f"node {node_id!r} not found in org {org.id}")

    @staticmethod
    def _contract_for(agent: Agent) -> tuple[str, str]:
        """The node's primary deliverable contract, from its own responsibilities. Defaults to a
        generic artifact when the node declares none (the catalog role's contracts arrive in E3)."""
        for r in agent.extensions.responsibilities:
            return r.deliverable.kind, r.deliverable.type
        return "artifact", "Deliverable"

    # --------------------------------------------------------------- intent intake
    def submit_intent(
        self, org_id: str, actuation_id: str, text: str, *, target_node: str | None = None,
        kind: str = "episodic", created_by: str = "operator", allowance_override: int | None = None,
        contract_kind: str | None = None, contract_type: str | None = None,
    ) -> RootAssignmentResult:
        """Create a work_intent and its root Assignment, funded from the target node's salary.

        The root Assignment is born ``briefed`` with brief v1 = the intent text; its meter is
        assignment-bound (task_id = the assignment id) — the D1 close. Delivery/wake of the node is
        the runtime's concern (E1 item 4); here we establish the durable work truth.
        """
        org = self._org(org_id)
        agent = self._node(org, target_node)
        allowance = allowance_override or agent.salary.perAssignmentAllowance
        ckind = contract_kind or self._contract_for(agent)[0]
        ctype = contract_type or self._contract_for(agent)[1]

        intent = self.store.create_intent(
            org_id, actuation_id, agent.id, text, kind=kind, created_by=created_by,
        )
        # Pre-mint the assignment id so the meter is bound to it in both directions.
        aid = new_assignment_id()
        meter = self.ledger.open_meter(
            actuation_id, agent.id, allowance,
            warn_threshold_pct=agent.salary.warnThresholdPct, hard_stop=agent.salary.hardStop,
            task_id=aid,
        )
        assignment = self.store.create_assignment(
            assignment_id=aid, org_id=org_id, actuation_id=actuation_id, intent_id=intent.id,
            node_id=agent.id, issued_by=created_by, contract_kind=ckind, contract_type=ctype,
            meter_id=meter.id, state="briefed",
        )
        self.store.add_brief(aid, text, revised_by=created_by)
        self.store.set_intent_root(intent.id, aid)
        self._log("intent.submitted", org_id, [intent.id, aid, agent.id],
                  {"actuationId": actuation_id, "meterId": meter.id})
        return RootAssignmentResult(intent=self.store.get_intent(intent.id), assignment=assignment)

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
        session_span_id: str | None = None,
    ):
        """Record an observable Step. Money was already metered by the gateway when it made the
        model call (shared ``step_id``); this row carries the delta taxonomy for introspection."""
        self._require(assignment_id)
        return self.store.add_step(
            assignment_id, input_tokens=input_tokens, output_tokens=output_tokens,
            duration_ms=duration_ms, kind=kind, stage_idx=stage_idx, delta_kind=delta_kind,
            delta_ref=delta_ref, step_id=step_id, session_span_id=session_span_id,
        )

    def update_stage(self, assignment_id: str, idx: int, state: str) -> None:
        """Advance a plan stage (the runtime's ``stage-update`` report). No-op if no plan yet."""
        plan = self.store.get_plan(assignment_id)
        if plan is not None:
            self.store.set_stage_state(plan.id, idx, state)

    def put_artifact(
        self, assignment_id: str, name: str, type: str, content: bytes, *,
        filename: str | None = None,
    ) -> ArtifactMeta:
        """Store an output in the Artifact Store under the assignment's org/node (grant checks in
        E3). The returned ``ref`` is what ``finish`` carries as the deliverable."""
        a = self._require(assignment_id)
        org = self._org(a.orgId)
        return self.artifacts.put(
            a.orgId, _slugify(org.name), a.nodeId, name, type, content,
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
        self._log("assignment.delivering", a.orgId, [assignment_id, deliverable.id],
                  {"refs": deliverable.artifactRefs})
        return deliverable

    # ------------------------------------------------------------------ acceptance
    def accept(self, assignment_id: str, note: str | None = None) -> Assignment:
        """Accept the deliverable: close the assignment + meter, write memory, and — for a root
        assignment — complete its intent."""
        a = self._require(assignment_id)
        if a.deliverableId is None:
            raise WorkError(f"assignment {assignment_id} has no deliverable to accept")
        self.store.review_deliverable(a.deliverableId, True, note)
        self.store.set_assignment_state(assignment_id, "accepted")
        self.ledger.close_meter(a.meterId)
        self._write_memory(a, outcome="accepted")
        self.store.set_assignment_state(assignment_id, "closed")
        if a.parentId is None:
            self.store.close_intent(a.intentId, "completed")
            self._log("intent.completed", a.orgId, [a.intentId, assignment_id], {})
        return self._require(assignment_id)

    def reject(
        self, assignment_id: str, note: str, *, revised_brief: str | None = None,
    ) -> Assignment:
        """Reject the deliverable and re-queue to ``planning`` for rework. The brief-version rework
        funding rule is E2; here a revised brief is simply recorded if supplied."""
        a = self._require(assignment_id)
        if a.deliverableId is None:
            raise WorkError(f"assignment {assignment_id} has no deliverable to reject")
        self.store.review_deliverable(a.deliverableId, False, note)
        if revised_brief is not None:
            self.store.add_brief(assignment_id, revised_brief, revised_by=a.issuedBy)
        self.store.set_assignment_state(assignment_id, "rejected")
        self.store.set_assignment_state(assignment_id, "planning")
        self._log("assignment.rejected", a.orgId, [assignment_id], {"note": note})
        return self._require(assignment_id)

    # --------------------------------------------------------------------- helpers
    def _write_memory(self, a: Assignment, *, outcome: str) -> None:
        intent = self.store.get_intent(a.intentId)
        meter = self.ledger.get_meter(a.meterId)
        deliverable = self.store.get_deliverable(a.deliverableId) if a.deliverableId else None
        self.store.append_memory(a.orgId, a.nodeId, {
            "assignmentId": a.id,
            "intentText": intent.text if intent else "",
            "outcome": outcome,
            "summary": deliverable.summary if deliverable else "",
            "costTokens": meter.spent if meter else 0,
        })

    def _log(self, action: str, org_id: str, subject_ids: list[str], payload: dict) -> None:
        if self.activity is not None:
            self.activity.log("system", action, org_id=org_id, subject_ids=subject_ids,
                              payload=payload)
