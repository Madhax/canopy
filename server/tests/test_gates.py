"""E2a golden vectors — staged delegation, dependency thresholds, rework funding, manager-await.

The vector list follows testing.md §4 (E2) and doubles as the build spec (rule 1: every
work-model §2.1 transition ships with a vector). The fixture team is the amended catalog's
product-engineering pod: lead + backend + frontend + qa, with the QA dependency edges declared
``resolveOn: delivered`` (verify) in the formation itself.
"""

from __future__ import annotations

import pytest


def _node(team: dict, role_key: str) -> dict:
    return next(a for a in team["agents"] if a["role"]["key"] == role_key)


@pytest.fixture()
def pod(client, make_org, mint_session):
    """A product-engineering pod with its lead executing a root (checkpointed) assignment."""
    from canopy_server.deps import get_engine

    team = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead = _node(team, "engineering-lead")
    s = mint_session(team["id"], node_id=lead["id"])
    eng = get_engine()
    root = eng.submit_intent(
        team["id"], s["actuationId"], "Add CSV export; all tests must pass",
        target_node=lead["id"],
    ).assignment
    eng.mark_intake_complete(root.id)
    eng.declare_plan(root.id, [{"title": "decompose"}, {"title": "review"}])
    return {
        "engine": eng, "team": team, "root": root, "lead": lead,
        "backend": _node(team, "backend-engineer"), "frontend": _node(team, "frontend-engineer"),
        "qa": _node(team, "qa-engineer"), "session": s,
    }


# --------------------------------------------------------------------- delegation invariants
def test_delegate_requires_direct_report(pod):
    from canopy_server.engine.engine import WorkError

    eng, root = pod["engine"], pod["root"]
    with pytest.raises(WorkError, match="not a report"):
        eng.delegate(root.id, "a_nobody", "do something")


def test_delegate_requires_executing_caller(pod, make_org, mint_session):
    from canopy_server.deps import get_engine
    from canopy_server.engine.engine import WorkError

    team = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"},
                   name="Second")
    lead = _node(team, "engineering-lead")
    s = mint_session(team["id"], node_id=lead["id"])
    eng = get_engine()
    root = eng.submit_intent(team["id"], s["actuationId"], "x", target_node=lead["id"]).assignment
    with pytest.raises(WorkError, match="delegate invalid"):  # still 'briefed'
        eng.delegate(root.id, _node(team, "backend-engineer")["id"], "too early")


# ------------------------------------------------------------------------ staged delegation
def test_proposed_drafts_hold_no_meter_and_publish_nothing(pod):
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement CSV export")
    qa = eng.delegate(
        root.id, pod["qa"]["id"], "verify the CSV export",
        depends_on=[{"assignmentId": be.id}],
    )
    assert be.state == "proposed" and qa.state == "proposed"
    assert be.meterId is None and qa.meterId is None  # unfunded drafts (work-model §2)
    # Nothing is published: the node's runtime cannot see a proposed draft.
    assert eng.store.current_assignment(root.teamId, pod["backend"]["id"]) is None

    gate = eng.finish_turn(root.id)
    assert gate is not None and gate.kind == "approval" and gate.owner == "operator"
    batch = gate.payload["batch"]
    assert [b["assignmentId"] for b in batch] == [be.id, qa.id]
    # The operator reviews the real delegations: briefs, contracts, deps with thresholds.
    qa_entry = next(b for b in batch if b["assignmentId"] == qa.id)
    assert qa_entry["dependsOn"][0]["upstreamId"] == be.id
    assert qa_entry["dependsOn"][0]["resolveOn"] == "delivered"  # the formation's verify edge
    assert qa_entry["allowance"] == pod["qa"]["salary"]["perAssignmentAllowance"]
    assert eng.store.get_assignment(root.id).state == "gated"


def test_approve_funds_and_dispatches_atomically(pod):
    from canopy_server.deps import get_ledger

    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    qa = eng.delegate(root.id, pod["qa"]["id"], "verify",
                      depends_on=[{"assignmentId": be.id}])
    gate = eng.finish_turn(root.id)

    eng.resolve_gate(gate.id, action="approve")

    be2, qa2 = eng.store.get_assignment(be.id), eng.store.get_assignment(qa.id)
    assert be2.state == "briefed" and be2.meterId is not None  # proposed → briefed, funded
    assert qa2.state == "gated" and qa2.meterId is not None  # born gated(dependency), funded
    for a, node in ((be2, pod["backend"]), (qa2, pod["qa"])):
        meter = get_ledger().get_meter(a.meterId)
        assert meter.taskId == a.id  # assignment-bound (D1 both directions)
        assert meter.allowance == node["salary"]["perAssignmentAllowance"]
        assert meter.spent == 0  # the padlock burns nothing
    # The manager's suspension continues directly as its await gate — no wasted wake.
    assert eng.store.get_assignment(root.id).state == "gated"
    awaits = [g for g in eng.store.list_gates(assignment_id=root.id, state="open")
              if g.payload.get("await")]
    assert len(awaits) == 1 and set(awaits[0].payload["children"]) == {be.id, qa.id}


def test_deny_cancels_drafts_as_prohibition(pod):
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    gate = eng.finish_turn(root.id)

    eng.resolve_gate(gate.id, action="deny", payload={"note": "wrong decomposition"})

    be2 = eng.store.get_assignment(be.id)
    assert be2.state == "cancelled" and be2.meterId is None  # proposed → cancelled, never funded
    assert eng.store.get_assignment(root.id).state == "executing"  # the manager re-plans
    g = eng.store.get_gate(gate.id)
    assert g.state == "resolved" and g.resolution["cancelled"] == [be.id]


def test_edit_draft_amends_brief_before_dispatch(pod):
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement CSV")
    gate = eng.finish_turn(root.id)

    eng.resolve_gate(gate.id, action="edit-draft", resolved_by="operator",
                     payload={"assignmentId": be.id, "brief": "implement CSV with RFC 4180"})

    g = eng.store.get_gate(gate.id)
    assert g.state == "open"  # editing is not the verdict
    assert g.payload["batch"][0]["brief"] == "implement CSV with RFC 4180"
    eng.resolve_gate(gate.id, action="approve")
    brief = eng.store.get_brief(be.id)
    # Versioning starts at dispatch: the amended draft IS v1 — no rework-funding trace.
    assert brief.version == 1 and brief.text == "implement CSV with RFC 4180"


def test_direct_delegation_dispatches_immediately(pod, monkeypatch):
    """A non-checkpointed manager's delegate funds and dispatches in one move (engine.md §2
    steps 3–6). Checkpointing is policy, so the vector pins the direct branch by policy override."""
    from canopy_server.engine.engine import ExecutionEngine

    monkeypatch.setattr(ExecutionEngine, "_checkpointed", staticmethod(lambda a: False))
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    assert be.state == "briefed" and be.meterId is not None
    # Published: the node's runtime sees it.
    assert eng.store.current_assignment(root.teamId, pod["backend"]["id"]).id == be.id


# ------------------------------------------------------------------- dependency thresholds
def _approved_fanout(pod, *, qa_resolve_on=None):
    """Fan out backend + qa(dependsOn backend) and approve the batch."""
    eng, root = pod["engine"], pod["root"]
    dep = {"assignmentId": None, **({"resolveOn": qa_resolve_on} if qa_resolve_on else {})}
    be = eng.delegate(root.id, pod["backend"]["id"], "implement", contract_type="PullRequest")
    dep["assignmentId"] = be.id
    qa = eng.delegate(root.id, pod["qa"]["id"], "verify", contract_type="TestReport",
                      depends_on=[dep])
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")
    return be, qa


def _drive_to_delivering(eng, assignment_id, refs, summary="done"):
    eng.mark_intake_complete(assignment_id)
    eng.declare_plan(assignment_id, [{"title": "work"}])
    return eng.finish(assignment_id, artifact_refs=refs, summary=summary)


def test_verify_dependency_resolves_at_finish(pod):
    eng = pod["engine"]
    be, qa = _approved_fanout(pod)  # formation edge: verify (delivered)

    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"])

    qa2 = eng.store.get_assignment(qa.id)
    assert qa2.state == "briefed"  # unlocked at SUBMISSION — acceptance not required
    brief = eng.store.get_brief(qa.id)
    assert "team://acme/be/pr@1" in brief.artifactRefs  # refs pinned at the submitted version
    assert brief.revisedBy == "system"  # exempt from the rework-funding rule


def test_consume_dependency_waits_for_acceptance(pod):
    eng = pod["engine"]
    be, qa = _approved_fanout(pod, qa_resolve_on="accepted")  # explicit consume edge

    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"])
    assert eng.store.get_assignment(qa.id).state == "gated"  # delivery is not enough

    eng.accept(be.id)
    qa2 = eng.store.get_assignment(qa.id)
    assert qa2.state == "briefed"  # consume resolves only at sign-off
    assert "team://acme/be/pr@1" in eng.store.get_brief(qa.id).artifactRefs


def test_dependency_sweep_is_idempotent_under_redelivery(pod):
    eng = pod["engine"]
    be, qa = _approved_fanout(pod)
    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"])

    # Redelivered report: the same sweep runs again — nothing double-resolves or double-grants.
    resolved = eng.gates.sweep(eng.store.get_assignment(be.id), "delivered",
                               ["team://acme/be/pr@1"])
    assert resolved == []
    brief = eng.store.get_brief(qa.id)
    assert brief.artifactRefs.count("team://acme/be/pr@1") == 1
    assert eng.store.get_assignment(qa.id).state == "briefed"


# ------------------------------------------------------------------------- rework funding
def test_rework_on_unchanged_brief_burns_the_same_meter(pod):
    from canopy_server.deps import get_ledger

    eng = pod["engine"]
    be, _qa = _approved_fanout(pod)
    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"])
    meter_before = get_ledger().get_meter(eng.store.get_assignment(be.id).meterId)

    eng.reject(be.id, "acceptance suite fails")  # brief unchanged

    be2 = eng.store.get_assignment(be.id)
    assert be2.state == "planning" and be2.briefVersion == 1
    meter_after = get_ledger().get_meter(be2.meterId)
    assert meter_after.id == meter_before.id  # same meter keeps burning
    assert meter_after.allowance == meter_before.allowance  # no top-up


def test_revised_brief_rework_transfers_from_parent_meter(pod):
    from canopy_server.deps import get_ledger

    eng, root = pod["engine"], pod["root"]
    be, _qa = _approved_fanout(pod)
    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"])

    ledger = get_ledger()
    child_before = ledger.get_meter(eng.store.get_assignment(be.id).meterId)
    parent_before = ledger.get_meter(root.meterId)

    eng.reject(be.id, "scope was wrong", revised_brief="also stream large exports")

    be2 = eng.store.get_assignment(be.id)
    assert be2.briefVersion == 2 and be2.state == "planning"
    child_after = ledger.get_meter(be2.meterId)
    parent_after = ledger.get_meter(root.meterId)
    grant = child_after.allowance - child_before.allowance
    assert grant == int(child_before.allowance * 20 / 100)  # the configured rework grant
    # The transfer nets to zero: the parent's spend rises by exactly the child's raise.
    assert parent_after.spent - parent_before.spent == grant
    # And it is visible in the ledger as a canopy/meter-transfer SpendEvent.
    transfers = [r for r in ledger.rollup(root.teamId, "model") if r["key"] == "meter-transfer"]
    assert transfers and transfers[0]["input_tokens"] + transfers[0]["output_tokens"] == grant


def test_root_revised_brief_rework_needs_no_parent_transfer(pod):
    """The root's parent is the intent — its 'meter' is the operator's explicit top-up, so a
    revised root brief re-versions without any transfer."""
    from canopy_server.deps import get_ledger

    eng, root = pod["engine"], pod["root"]
    eng.finish(root.id, artifact_refs=[], summary="attempt")
    before = get_ledger().get_meter(root.meterId)
    eng.reject(root.id, "not quite", revised_brief="tighter scope")
    after = get_ledger().get_meter(root.meterId)
    assert after.allowance == before.allowance  # untouched — top-ups are gate resolutions
    assert eng.store.get_assignment(root.id).briefVersion == 2


# ---------------------------------------------------------------------------- manager-await
def test_manager_await_wakes_per_delivery_and_rearms(pod):
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    fe = eng.delegate(root.id, pod["frontend"]["id"], "implement UI")
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")
    assert eng.store.get_assignment(root.id).state == "gated"  # awaiting reports

    # Wake 1: the first child delivers while the second still works.
    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"], summary="backend done")
    assert eng.store.get_assignment(root.id).state == "executing"
    await_gates = [g for g in eng.store.list_gates(assignment_id=root.id, state="resolved")
                   if g.payload.get("await")]
    res = await_gates[-1].resolution
    assert [p["assignmentId"] for p in res["pending"]] == [be.id]
    assert set(res["outstanding"]) == {be.id, fe.id}  # the remainder rides along

    # The manager reviews what arrived, then re-enters the gate while children remain.
    eng.accept(be.id)
    gate2 = eng.finish_turn(root.id)
    assert gate2 is not None and gate2.payload["children"] == [fe.id]
    assert eng.store.get_assignment(root.id).state == "gated"

    # Wake 2: the second child delivers.
    _drive_to_delivering(eng, fe.id, ["team://acme/fe/ui@1"], summary="frontend done")
    assert eng.store.get_assignment(root.id).state == "executing"
    eng.accept(fe.id)
    assert eng.finish_turn(root.id) is None  # child set drained — no re-arm


def test_finish_turn_sweeps_deliveries_that_arrived_mid_review(pod):
    """A child delivering while the manager is executing (no open await gate) must not be a
    missed wake: the re-arm sweeps immediately."""
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    fe = eng.delegate(root.id, pod["frontend"]["id"], "implement UI")
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")

    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"])  # wake 1
    # While the manager reviews, the OTHER child also delivers — no gate is open right now.
    _drive_to_delivering(eng, fe.id, ["team://acme/fe/ui@1"])
    eng.accept(be.id)

    eng.finish_turn(root.id)  # re-arm must immediately resolve on fe's pending deliverable
    assert eng.store.get_assignment(root.id).state == "executing"


def test_await_arm_races_child_delivery(pod, monkeypatch):
    """The E6 wake-loss race, deterministically: a child's finish-sweep runs BETWEEN the
    await-gate insert and the manager's suspend. The sweep resolves the gate but (correctly)
    refuses to restore a not-yet-gated manager — the open path must then notice it suspended
    on an already-resolved gate and undo it, or the manager sleeps forever."""
    eng, root = pod["engine"], pod["root"]
    store, svc = eng.store, eng.gates
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")

    # First wake, consumed normally: root back to executing, no open gate, child delivering.
    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"])
    assert store.get_assignment(root.id).state == "executing"

    # Now the manager re-arms — and the child's sweep fires inside the race window.
    orig_create = store.create_gate
    fired = []
    def racing_create(assignment_id, kind, **kw):
        g = orig_create(assignment_id, kind, **kw)
        if kw.get("payload", {}).get("await") and not fired:
            fired.append(True)
            # T2 wins the window: the manager is still 'executing', so this resolves the
            # freshly inserted gate without restoring anyone.
            svc.sweep(store.get_assignment(be.id), "delivered", ["team://acme/be/pr@1"])
            assert store.get_gate(g.id).state == "resolved"
        return g

    monkeypatch.setattr(store, "create_gate", racing_create)
    eng.finish_turn(root.id)
    assert fired  # the race actually interleaved
    a = store.get_assignment(root.id)
    assert a.state == "executing"  # NOT gated-forever on a resolved gate
    assert svc.open_gate_for(root.id, "dependency") is None


# ------------------------------------------------------------------- the demo, as a fixture
def test_mvp_demo_ordering(pod):
    """mvp.md §3.7–3.9 as an executable fixture: submit → verify-dep resolves → QA fails →
    reject on the still-open assignment → rework on the same meter → re-verify → accept.
    Acceptance never precedes the green report (mvp §5, asserted not narrated)."""
    from canopy_server.deps import get_ledger

    eng, root = pod["engine"], pod["root"]
    be, qa = _approved_fanout(pod)

    # Engineer submits PR@1 — QA's verify gate resolves at submission; the lead holds acceptance.
    _drive_to_delivering(eng, be.id, ["team://acme/be/pr@1"], summary="PR v1")
    assert eng.store.get_assignment(qa.id).state == "briefed"
    assert eng.store.get_assignment(be.id).state == "delivering"

    # QA runs the suite: red. The lead rejects the engineer's STILL-OPEN deliverable.
    _drive_to_delivering(eng, qa.id, ["team://acme/qa/report@1"], summary="FAIL: edge case")
    be_meter_id = eng.store.get_assignment(be.id).meterId
    assert eng.store.get_assignment(be.id).state == "delivering"  # never closed early
    eng.reject(be.id, "TestReport team://acme/qa/report@1 cites a failing edge case")
    be2 = eng.store.get_assignment(be.id)
    assert be2.state == "planning" and be2.meterId == be_meter_id  # same assignment, same meter
    assert be2.briefVersion == 1  # brief unchanged — quality failure, engineer's tab

    # Rework: PR@2. Re-verification is a rework round on QA, citing the new version.
    eng.finish(be.id, artifact_refs=["team://acme/be/pr@2"], summary="PR v2")
    eng.reject(qa.id, "re-verify against PR@2",
               revised_brief="verify team://acme/be/pr@2; all tests must pass")
    green = eng.finish(qa.id, artifact_refs=["team://acme/qa/report@2"], summary="PASS")

    # Acceptance is the final verdict, informed by verification — and provably after it.
    eng.accept(qa.id)
    eng.accept(be.id)
    be3, qa3 = eng.store.get_assignment(be.id), eng.store.get_assignment(qa.id)
    assert be3.state == "closed" and qa3.state == "closed"
    assert green.createdAt <= be3.closedAt  # the green report precedes the engineer's close

    # Money replay (testing.md §4): every token spent anywhere is attributable.
    ledger = get_ledger()
    by_node = ledger.rollup(root.teamId, "node")
    total_events = sum(r["input_tokens"] + r["output_tokens"] for r in by_node)
    meters = [ledger.get_meter(m) for m in
              {root.meterId, be3.meterId, qa3.meterId} if m]
    assert total_events == sum(m.spent for m in meters)


def test_spend_rollup_by_intent_with_split(pod, client):
    """The E5 cost-explorer feed: groupBy=intent attributes every SpendEvent to its intent via
    the assignment; split=true separates coordination from production (SC-1)."""
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")
    eng.mark_intake_complete(be.id)
    eng.declare_plan(be.id, [{"title": "work"}])
    eng.record_step(be.id, input_tokens=100, output_tokens=20, duration_ms=5,
                    settle=True, kind="production", step_id="st_prod1")
    eng.record_step(root.id, input_tokens=40, output_tokens=10, duration_ms=5,
                    settle=True, kind="coordination", step_id="st_coord1")

    r = client.get(f"/api/teams/{root.teamId}/spend?groupBy=intent&split=true").json()
    row = next(x for x in r["rows"] if x["key"] == root.intentId)
    assert row["coordination_tokens"] == 50 and row["production_tokens"] == 120
    by_assignment = client.get(
        f"/api/teams/{root.teamId}/spend?groupBy=assignment"
    ).json()["rows"]
    assert {x["key"] for x in by_assignment} >= {root.id, be.id}
