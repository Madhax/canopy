"""WorkStore — the work-model persistence layer (work-model.md)."""

from __future__ import annotations

from canopy_server.db import Db
from canopy_server.engine.store import WorkStore


def _store(tmp_path) -> WorkStore:
    return WorkStore(Db(tmp_path / "canopy.db"))


def _assignment(store: WorkStore, **kw):
    """Create a root assignment with sensible defaults for tests that don't care about the shape."""
    defaults = dict(
        org_id="o1", actuation_id="act_1", intent_id="in_x", node_id="a_be", issued_by="operator",
        contract_kind="artifact", contract_type="PullRequest", meter_id="mt_1",
    )
    defaults.update(kw)
    return store.create_assignment(**defaults)


# ------------------------------------------------------------------- intents
def test_intent_roundtrip_and_root_link(tmp_path):
    store = _store(tmp_path)
    intent = store.create_intent("o1", "act_1", "a_root", "Add CSV export")
    assert intent.state == "open" and intent.kind == "episodic" and intent.createdBy == "operator"
    assert store.get_intent(intent.id).text == "Add CSV export"

    store.set_intent_root(intent.id, "as_root")
    assert store.get_intent(intent.id).rootAssignmentId == "as_root"

    store.close_intent(intent.id, "completed")
    closed = store.get_intent(intent.id)
    assert closed.state == "completed" and closed.closedAt is not None


def test_list_intents_newest_first(tmp_path):
    store = _store(tmp_path)
    a = store.create_intent("o1", "act_1", "a_root", "first")
    b = store.create_intent("o1", "act_1", "a_root", "second")
    store.create_intent("o2", "act_9", "a_root", "other org")
    ids = [i.id for i in store.list_intents("o1")]
    assert ids == [b.id, a.id]  # DESC by created_at


# --------------------------------------------------------------- assignments
def test_assignment_create_and_state_machine(tmp_path):
    store = _store(tmp_path)
    a = _assignment(store, state="briefed")
    assert a.state == "briefed" and a.briefVersion == 1 and a.parentId is None

    store.set_assignment_state(a.id, "executing")
    assert store.get_assignment(a.id).state == "executing"
    assert store.get_assignment(a.id).closedAt is None

    store.set_assignment_state(a.id, "closed")
    closed = store.get_assignment(a.id)
    assert closed.state == "closed" and closed.closedAt is not None  # terminal stamps closed_at


def test_current_assignment_ignores_terminal(tmp_path):
    store = _store(tmp_path)
    assert store.current_assignment("act_1", "a_be") is None
    a = _assignment(store, state="executing")
    assert store.current_assignment("act_1", "a_be").id == a.id

    store.set_assignment_state(a.id, "closed")
    assert store.current_assignment("act_1", "a_be") is None  # closed no longer "current"


def test_list_assignments_filters(tmp_path):
    store = _store(tmp_path)
    be = _assignment(store, node_id="a_be", state="executing")
    _assignment(store, node_id="a_qa", state="gated", intent_id="in_y")
    assert len(store.list_assignments(org_id="o1")) == 2
    assert [x.id for x in store.list_assignments(node_id="a_be")] == [be.id]
    assert [x.id for x in store.list_assignments(state="gated")][0] != be.id
    assert [x.id for x in store.list_assignments(intent_id="in_x")] == [be.id]


def test_deliverable_and_session_refs_stick(tmp_path):
    store = _store(tmp_path)
    a = _assignment(store)
    store.set_deliverable_ref(a.id, "dv_1")
    store.set_session_ref(a.id, "sess-abc")
    got = store.get_assignment(a.id)
    assert got.deliverableId == "dv_1" and got.sessionRef == "sess-abc"


# --------------------------------------------------------------------- briefs
def test_brief_versioning_bumps_assignment(tmp_path):
    store = _store(tmp_path)
    a = _assignment(store)
    v1 = store.add_brief(a.id, "do the thing", artifact_refs=["org://acme/a_be/spec@1"])
    assert v1.version == 1 and v1.artifactRefs == ["org://acme/a_be/spec@1"]

    v2 = store.add_brief(a.id, "do it better", revised_by="a_lead")
    assert v2.version == 2 and v2.revisedBy == "a_lead"
    assert store.get_assignment(a.id).briefVersion == 2  # stamped on the assignment
    assert store.get_brief(a.id).version == 2             # latest by default
    assert store.get_brief(a.id, 1).text == "do the thing"
    assert [b.version for b in store.list_briefs(a.id)] == [1, 2]


# ---------------------------------------------------------------------- plans
def test_plan_versioning_and_stages(tmp_path):
    store = _store(tmp_path)
    a = _assignment(store)
    p1 = store.create_plan(a.id, [
        {"title": "scaffold", "completion": "endpoint stubbed"},
        {"title": "implement", "sizing": "large", "envelopeTokens": 40000},
    ])
    assert p1.version == 1 and len(p1.stages) == 2
    assert p1.stages[0].title == "scaffold" and p1.stages[0].state == "pending"
    assert p1.stages[1].sizing == "large" and p1.stages[1].envelopeTokens == 40000

    store.set_stage_state(p1.id, 0, "done")
    assert store.get_plan(a.id).stages[0].state == "done"

    p2 = store.create_plan(a.id, [{"title": "redo"}])
    assert p2.version == 2 and store.get_plan(a.id).version == 2  # latest by default


# ---------------------------------------------------------------------- steps
def test_steps_append_and_list(tmp_path):
    store = _store(tmp_path)
    a = _assignment(store)
    store.add_step(a.id, input_tokens=100, output_tokens=50, duration_ms=1200,
                   delta_kind="artifact", delta_ref="org://acme/a_be/pr@1", stage_idx=1)
    store.add_step(a.id, input_tokens=10, output_tokens=5, duration_ms=300, kind="coordination")
    steps = store.list_steps(a.id)
    assert len(steps) == 2
    assert steps[0].deltaKind == "artifact" and steps[0].stageIdx == 1
    assert steps[1].kind == "coordination" and steps[1].deltaKind == "none"


# --------------------------------------------------------------- deliverables
def test_deliverable_create_and_review(tmp_path):
    store = _store(tmp_path)
    a = _assignment(store)
    d = store.create_deliverable(a.id, "artifact", artifact_refs=["org://acme/a_be/pr@1"],
                                 summary="PR ready")
    assert d.accepted is None and d.artifactRefs == ["org://acme/a_be/pr@1"]

    rejected = store.review_deliverable(d.id, False, "one test fails")
    assert rejected.accepted is False and rejected.reviewNote == "one test fails"
    assert rejected.reviewedAt is not None

    accepted = store.review_deliverable(d.id, True)
    assert accepted.accepted is True


def test_attestation_deliverable(tmp_path):
    store = _store(tmp_path)
    a = _assignment(store, contract_kind="attestation", contract_type="ActionAttestation")
    att = {"claim": "emailed the lead", "evidenceRefs": ["org://acme/a_be/log@1"], "at": "now"}
    d = store.create_deliverable(a.id, "attestation", attestation=att)
    got = store.get_deliverable(d.id)
    assert got.kind == "attestation" and got.attestation["claim"] == "emailed the lead"


# --------------------------------------------------------------------- memory
def test_memory_append_get_reset(tmp_path):
    store = _store(tmp_path)
    for i in range(3):
        store.append_memory("o1", "a_be", {"assignmentId": f"as_{i}", "summary": f"did {i}"})
    entries = store.get_memory("o1", "a_be")
    assert [e.seq for e in entries] == [1, 2, 3]                 # oldest → newest
    assert entries[-1].entry["summary"] == "did 2"

    assert [e.seq for e in store.get_memory("o1", "a_be", limit=2)] == [2, 3]  # last N
    assert store.get_memory("o1", "a_qa") == []                  # scoped per node

    store.reset_memory("o1", "a_be")
    assert store.get_memory("o1", "a_be") == []
    # seq restarts after a reset (position backfilled)
    assert store.append_memory("o1", "a_be", {"x": 1}).seq == 1
