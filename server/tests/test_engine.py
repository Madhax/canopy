"""ExecutionEngine — intent intake, the E1 happy path, and the D1 metering close.

Uses the real app harness (``client`` points ``CANOPY_DATA_DIR`` at a temp dir, so the engine,
ledger, org store, and gateway all share one database) with the ``mint_session`` fixture for the
run-token/profile path.
"""

from __future__ import annotations


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _root_of(org: dict) -> dict:
    return next(a for a in org["agents"] if a["managerId"] is None)


def test_intent_creates_funded_root_assignment(client, make_org, mint_session):
    from canopy_server.deps import get_engine, get_ledger

    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])

    res = get_engine().submit_intent(
        org["id"], s["actuationId"], "Add CSV export to the report endpoints",
        target_node=root["id"],
    )
    intent, a = res.intent, res.assignment
    assert intent.state == "open" and intent.rootAssignmentId == a.id
    assert a.state == "briefed" and a.parentId is None and a.briefVersion == 1
    assert a.issuedBy == "operator"

    # The meter is assignment-bound (D1): its own meter, funded from the node's salary.
    meter = get_ledger().get_meter(a.meterId)
    assert meter.allowance == root["salary"]["perAssignmentAllowance"]
    assert meter.taskId == a.id and meter.spent == 0

    brief = get_engine().store.get_brief(a.id)
    assert brief.version == 1 and brief.text.startswith("Add CSV export")


def test_happy_path_intent_to_closed(client, make_org, mint_session):
    from canopy_server.deps import get_engine

    eng = get_engine()
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])

    a = eng.submit_intent(org["id"], s["actuationId"], "ship CSV export",
                          target_node=root["id"]).assignment

    eng.mark_intake_complete(a.id)
    assert eng.store.get_assignment(a.id).state == "planning"

    eng.declare_plan(a.id, [{"title": "implement"}, {"title": "test"}])
    assert eng.store.get_assignment(a.id).state == "executing"

    eng.record_step(a.id, input_tokens=100, output_tokens=40, duration_ms=900,
                    delta_kind="progress", delta_ref="0", stage_idx=0)
    art = eng.put_artifact(a.id, "csv-export", "code-patch", b"col1,col2\n1,2\n")
    assert art.ref.endswith("/csv-export@1")

    deliverable = eng.finish(a.id, artifact_refs=[art.ref], summary="CSV export implemented")
    assert eng.store.get_assignment(a.id).state == "delivering"
    assert deliverable.artifactRefs == [art.ref] and deliverable.accepted is None

    closed = eng.accept(a.id, note="looks good")
    assert closed.state == "closed" and closed.closedAt is not None
    assert eng.store.get_intent(a.intentId).state == "completed"  # root close → intent completed
    assert eng.store.get_deliverable(deliverable.id).accepted is True

    # Closing writes one durable memory entry for the node (survives re-actuation).
    mem = eng.store.get_memory(org["id"], root["id"])
    assert len(mem) == 1 and mem[0].entry["outcome"] == "accepted"
    assert mem[0].entry["intentText"] == "ship CSV export"

    assert len(eng.store.list_steps(a.id)) == 1


def test_d1_completion_meters_the_assignment_meter(client, make_org, mint_session):
    """The gateway resolver charges the assignment-bound meter, not the node's default meter."""
    from canopy_server.deps import get_engine, get_ledger

    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])  # opens the node's DEFAULT meter
    a = get_engine().submit_intent(
        org["id"], s["actuationId"], "do the work", target_node=root["id"],
        allowance_override=50_000,
    ).assignment

    r = client.post(
        "/api/dp/llm/complete", headers=_headers(s["token"]),
        json={"messages": [{"role": "user", "content": "hello"}], "taskId": a.id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["meter"]["id"] == a.meterId  # the assignment meter, resolved from the task

    assert get_ledger().get_meter(a.meterId).spent > 0        # assignment meter charged
    assert get_ledger().get_meter(s["meterId"]).spent == 0    # default meter untouched (D1)


def test_reject_requeues_to_planning(client, make_org, mint_session):
    from canopy_server.deps import get_engine

    eng = get_engine()
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    a = eng.submit_intent(
        org["id"], s["actuationId"], "build it", target_node=root["id"]
    ).assignment
    eng.mark_intake_complete(a.id)
    eng.declare_plan(a.id, [{"title": "do"}])
    d = eng.finish(a.id, artifact_refs=[], summary="attempt 1")

    eng.reject(a.id, "an edge-case test fails", revised_brief="also handle empty rows")
    assert eng.store.get_assignment(a.id).state == "planning"
    assert eng.store.get_deliverable(d.id).accepted is False
    assert eng.store.get_assignment(a.id).briefVersion == 2  # revised brief recorded
