"""E2b golden vectors — judgment gates, triggers, reassignment, cancellation, notes, priority.

Continues the testing.md §4 (E2) vector list where test_gates.py (the delegation spine) left
off: clarification/escalation resolutions, X1 intervene, budget warn/hard-stop and stall
triggers, R2 reassignment carrying remaining balance, the cancel cascade leaving no orphan
gates, D-4 stage timestamps, and D-5 notes delivered exactly once.
"""

from __future__ import annotations

import pytest


def _node(team: dict, role_key: str) -> dict:
    return next(a for a in team["agents"] if a["role"]["key"] == role_key)


@pytest.fixture()
def pod(client, make_org, mint_session):
    """A product-engineering pod with its lead executing a root assignment (mirrors
    test_gates.pod; kept local so each vector file reads standalone)."""
    from canopy_server.deps import get_engine

    team = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead = _node(team, "engineering-lead")
    s = mint_session(team["id"], node_id=lead["id"])
    eng = get_engine()
    root = eng.submit_intent(
        team["id"], s["actuationId"], "Add CSV export", target_node=lead["id"],
    ).assignment
    eng.mark_intake_complete(root.id)
    eng.declare_plan(root.id, [{"title": "decompose"}, {"title": "review"}])
    return {
        "engine": eng, "team": team, "root": root, "lead": lead,
        "backend": _node(team, "backend-engineer"), "frontend": _node(team, "frontend-engineer"),
        "qa": _node(team, "qa-engineer"), "session": s,
    }


def _fanout_child(pod, node_key="backend", **delegate_kw):
    """Delegate one child from the root and approve the batch — returns the dispatched child."""
    eng, root = pod["engine"], pod["root"]
    child = eng.delegate(root.id, pod[node_key]["id"], "do the work", **delegate_kw)
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")
    return eng.store.get_assignment(child.id)


# ---------------------------------------------------------------- clarification / escalation
def test_clarification_resolved_by_revised_brief(pod):
    eng = pod["engine"]
    child = _fanout_child(pod)

    gate = eng.open_clarification(child.id, "which endpoints exactly?")
    assert gate.owner == pod["root"].nodeId  # the issuing manager owns it
    assert eng.store.get_assignment(child.id).state == "gated"

    eng.resolve_gate(gate.id, action="revise-brief", resolved_by=pod["root"].nodeId,
                     payload={"brief": "CSV export on /reports only"})
    c = eng.store.get_assignment(child.id)
    assert c.state == "briefed" and c.briefVersion == 2  # re-intake on the clarified brief
    assert eng.store.get_brief(child.id).text == "CSV export on /reports only"


def test_root_clarification_owned_by_operator(pod):
    eng, root = pod["engine"], pod["root"]
    # Re-enter intake territory: a fresh root in 'briefed' may raise clarification directly.
    org2_root = eng.submit_intent(
        root.teamId, root.actuationId, "vague ask", target_node=pod["lead"]["id"],
    ).assignment
    gate = eng.open_clarification(org2_root.id, "what does done mean?")
    assert gate.owner == "operator"


def test_escalation_answer_carries_refs_and_resumes(pod):
    eng = pod["engine"]
    child = _fanout_child(pod)
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "work"}])

    gate = eng.open_escalation(child.id, "may I change the schema?",
                               refs=["team://acme/be/draft@1"])
    assert eng.store.get_assignment(child.id).state == "gated"

    eng.resolve_gate(gate.id, action="answer", resolved_by=pod["root"].nodeId,
                     payload={"answer": "yes, additive only", "refs": ["team://acme/lead/policy@1"]})
    c = eng.store.get_assignment(child.id)
    assert c.state == "executing"  # resumes where it was
    assert "team://acme/lead/policy@1" in eng.store.get_brief(child.id).artifactRefs
    g = eng.store.get_gate(gate.id)
    assert g.resolution["answer"] == "yes, additive only"


def test_gate_state_preconditions(pod):
    from canopy_server.engine.engine import WorkError

    eng = pod["engine"]
    child = _fanout_child(pod)
    with pytest.raises(WorkError, match="escalation invalid"):
        eng.open_escalation(child.id, "too early")  # still briefed
    eng.mark_intake_complete(child.id)
    with pytest.raises(WorkError, match="clarification invalid"):
        eng.declare_plan(child.id, [{"title": "w"}])  # -> executing
        eng.open_clarification(child.id, "too late")


# ----------------------------------------------------------------------------- X1 intervene
def test_intervene_suspends_and_resume_restores(pod):
    eng, root = pod["engine"], pod["root"]
    gate = eng.intervene(root.id, "hold on, checking direction")
    assert gate.openedBy == "operator" and gate.kind == "intervention"
    assert eng.store.get_assignment(root.id).state == "gated"

    eng.resolve_gate(gate.id, action="resume")
    assert eng.store.get_assignment(root.id).state == "executing"


def test_intervene_topup_raises_meter(pod):
    from canopy_server.deps import get_ledger

    eng, root = pod["engine"], pod["root"]
    before = get_ledger().get_meter(root.meterId)
    gate = eng.intervene(root.id, "funding a bigger scope")
    eng.resolve_gate(gate.id, action="top-up", payload={"amount": 5000})
    after = get_ledger().get_meter(root.meterId)
    assert after.allowance == before.allowance + 5000
    assert eng.store.get_assignment(root.id).state == "executing"


# --------------------------------------------------------------------------------- triggers
def _exhaust(ledger, meter_id, *, team_id, node_id, actuation_id, step_id, tokens):
    res = ledger.reserve(meter_id, tokens)
    ledger.record(meter_id, step_id=step_id, team_id=team_id, node_id=node_id,
                  actuation_id=actuation_id, provider="mock", model="mock-1",
                  input_tokens=tokens, output_tokens=0, est_cost_micros=0,
                  reserved=res.amount)


def test_hard_stop_opens_intervention_and_topup_resumes(pod, make_org, mint_session):
    from canopy_server.deps import get_engine, get_ledger

    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"}, name="Tight")
    lead = next(a for a in team["agents"] if a["managerId"] is None)
    s = mint_session(team["id"], node_id=lead["id"])
    eng, ledger = get_engine(), get_ledger()
    a = eng.submit_intent(team["id"], s["actuationId"], "small budget",
                          target_node=lead["id"], allowance_override=100).assignment
    eng.mark_intake_complete(a.id)
    eng.declare_plan(a.id, [{"title": "w"}])

    _exhaust(ledger, a.meterId, team_id=team["id"], node_id=lead["id"],
             actuation_id=s["actuationId"], step_id="st_burn1", tokens=100)
    # The next step report evaluates the triggers: hard-stop gate + attention notification.
    eng.record_step(a.id, input_tokens=0, output_tokens=0, duration_ms=10, step_id="st_burn1")
    assert eng.store.get_assignment(a.id).state == "gated"
    gate = next(g for g in eng.store.list_gates(assignment_id=a.id, state="open")
                if g.openedBy == "trigger:hard-stop")
    kinds = [n.kind for n in eng.store.list_notifications(team["id"])]
    assert "hard-stop" in kinds

    # Top-up resolves the InterventionGate; the meter reopens; work resumes.
    eng.resolve_gate(gate.id, action="top-up", payload={"amount": 200})
    assert eng.store.get_assignment(a.id).state == "executing"
    assert ledger.get_meter(a.meterId).state == "open"

    # A second exhaustion is a NEW fact: a fresh gate opens (allowance is in the reason hash).
    _exhaust(ledger, a.meterId, team_id=team["id"], node_id=lead["id"],
             actuation_id=s["actuationId"], step_id="st_burn2", tokens=200)
    eng.record_step(a.id, input_tokens=0, output_tokens=0, duration_ms=10, step_id="st_burn2")
    assert eng.store.get_assignment(a.id).state == "gated"


def test_budget_warn_notifies_exactly_once(pod, make_org, mint_session):
    from canopy_server.deps import get_engine, get_ledger

    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"}, name="Warned")
    lead = next(a for a in team["agents"] if a["managerId"] is None)
    s = mint_session(team["id"], node_id=lead["id"])
    eng, ledger = get_engine(), get_ledger()
    a = eng.submit_intent(team["id"], s["actuationId"], "warn me",
                          target_node=lead["id"], allowance_override=1000).assignment
    eng.mark_intake_complete(a.id)
    eng.declare_plan(a.id, [{"title": "w"}])

    _exhaust(ledger, a.meterId, team_id=team["id"], node_id=lead["id"],
             actuation_id=s["actuationId"], step_id="st_w1", tokens=850)  # crosses 80%
    eng.record_step(a.id, input_tokens=0, output_tokens=0, duration_ms=5, step_id="st_w1")
    eng.record_step(a.id, input_tokens=0, output_tokens=0, duration_ms=5, step_id="st_w2")
    warns = [n for n in eng.store.list_notifications(team["id"]) if n.kind == "budget-warn"]
    assert len(warns) == 1  # deduped — the amber glow fires once
    assert eng.store.get_assignment(a.id).state == "executing"  # warn never suspends


def test_stall_sweep_quiet_assignment(pod):
    from canopy_server.deps import get_db

    eng = pod["engine"]
    child = _fanout_child(pod)
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "w"}])
    # Backdate the last activity beyond stall_minutes (no steps yet -> anchor is updated_at).
    with get_db().transaction() as conn:
        conn.execute("UPDATE work_assignment SET updated_at=? WHERE id=?",
                     ("2020-01-01T00:00:00+00:00", child.id))

    opened = eng.sweep_triggers()
    assert any(g.assignmentId == child.id for g in opened)
    assert eng.store.get_assignment(child.id).state == "gated"
    # The sweep is idempotent: a second pass never double-opens (and the child is gated anyway).
    assert eng.sweep_triggers() == []


def test_stall_sweep_no_delta_steps(pod):
    eng = pod["engine"]
    child = _fanout_child(pod)
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "w"}])
    for i in range(5):  # stall_none_steps default
        eng.record_step(child.id, input_tokens=10, output_tokens=1, duration_ms=5,
                        delta_kind="none", step_id=f"st_none{i}")

    opened = eng.sweep_triggers()
    assert any(g.assignmentId == child.id and "no-delta" in g.reason for g in opened)


# ------------------------------------------------------------------------------ R2 reassign
def test_reassign_carries_provenance_and_remaining_balance(pod):
    from canopy_server.deps import get_ledger

    eng = pod["engine"]
    child = _fanout_child(pod)  # backend
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "w"}])
    # Burn part of the budget, then reassign to the frontend engineer.
    _exhaust(get_ledger(), child.meterId, team_id=child.teamId, node_id=child.nodeId,
             actuation_id=child.actuationId, step_id="st_part", tokens=1000)
    old_meter = get_ledger().get_meter(child.meterId)
    remaining = old_meter.allowance - old_meter.spent

    gate = eng.intervene(child.id, "backend is overloaded")
    eng.resolve_gate(gate.id, action="reassign",
                     payload={"toNodeId": pod["frontend"]["id"]})

    old = eng.store.get_assignment(child.id)
    assert old.state == "cancelled"
    assert get_ledger().get_meter(old.meterId).state == "closed"
    replacement = next(a for a in eng.store.list_assignments(intent_id=child.intentId)
                       if a.reassignedFrom == child.id)
    assert replacement.nodeId == pod["frontend"]["id"] and replacement.state == "briefed"
    new_meter = get_ledger().get_meter(replacement.meterId)
    assert new_meter.allowance == remaining  # the balance travels, not a fresh salary
    assert eng.store.get_brief(replacement.id).text == "do the work"  # brief carried


def test_reassign_target_must_be_a_report(pod):
    from canopy_server.engine.engine import WorkError

    eng = pod["engine"]
    child = _fanout_child(pod)
    gate = eng.intervene(child.id, "move it")
    with pytest.raises(WorkError, match="not a report"):
        eng.resolve_gate(gate.id, action="reassign", payload={"toNodeId": "a_stranger"})


# --------------------------------------------------------------------------- cancel cascade
def test_cancel_cascades_children_meters_and_gates(pod):
    from canopy_server.deps import get_ledger

    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    qa = eng.delegate(root.id, pod["qa"]["id"], "verify",
                      depends_on=[{"assignmentId": be.id}])
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")

    eng.cancel_assignment(root.id, by="operator", reason="changed direction")

    for aid in (root.id, be.id, qa.id):
        a = eng.store.get_assignment(aid)
        assert a.state == "cancelled"
        if a.meterId:
            assert get_ledger().get_meter(a.meterId).state == "closed"
        assert eng.store.list_gates(assignment_id=aid, state="open") == []  # no orphan gates
    assert eng.store.get_intent(root.intentId).state == "cancelled"


# ------------------------------------------------------------------- notes, priority, plan
def test_notes_delivered_exactly_once_without_suspending(pod, client):
    eng, root = pod["engine"], pod["root"]
    s = pod["session"]
    note = eng.store.create_note(root.teamId, root.intentId, "prefer the streaming writer",
                                 assignment_id=root.id, stage_idx=0)
    assert note.deliveredAt is None

    cur = client.get("/api/dp/assignment/current",
                     headers={"Authorization": f"Bearer {s['token']}"}).json()
    assert [n["text"] for n in cur["notes"]] == ["prefer the streaming writer"]
    assert cur["notes"][0]["deliveredAt"] is not None
    assert cur["assignment"]["state"] == "executing"  # advisory — never a suspension

    cur2 = client.get("/api/dp/assignment/current",
                      headers={"Authorization": f"Bearer {s['token']}"}).json()
    assert cur2["notes"] == []  # injected exactly once


def test_priority_updates(pod):
    eng = pod["engine"]
    child = _fanout_child(pod)
    assert eng.set_priority(child.id, 7).priority == 7


def test_stage_timestamps_stamped(pod):
    eng, root = pod["engine"], pod["root"]
    eng.update_stage(root.id, 0, "active")
    plan = eng.store.get_plan(root.id)
    assert plan.stages[0].startedAt is not None and plan.stages[0].completedAt is None
    eng.update_stage(root.id, 0, "done")
    plan = eng.store.get_plan(root.id)
    assert plan.stages[0].completedAt is not None


def test_plan_aggregate_over_http(pod, client):
    eng, root = pod["engine"], pod["root"]
    be = eng.delegate(root.id, pod["backend"]["id"], "implement")
    qa = eng.delegate(root.id, pod["qa"]["id"], "verify",
                      depends_on=[{"assignmentId": be.id}])
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")
    client.post(f"/api/intents/{root.intentId}/notes",
                json={"text": "watch the encoding", "assignmentId": be.id})

    r = client.get(f"/api/intents/{root.intentId}/plan")
    assert r.status_code == 200
    tree = r.json()["tree"]
    assert len(tree) == 1 and tree[0]["assignment"]["id"] == root.id
    kids = {c["assignment"]["id"]: c for c in tree[0]["children"]}
    assert set(kids) == {be.id, qa.id}
    assert kids[qa.id]["gates"][0]["kind"] == "dependency"  # the padlock, visible in the plan
    assert [n["text"] for n in kids[be.id]["notes"]] == ["watch the encoding"]
    assert tree[0]["gates"][0]["payload"].get("await")  # the manager awaits its reports


def test_notifications_feed_and_read_cursor(pod, client):
    eng, root = pod["engine"], pod["root"]
    eng.delegate(root.id, pod["backend"]["id"], "implement")
    eng.finish_turn(root.id)  # -> plan-review-waiting notification

    r = client.get(f"/api/teams/{root.teamId}/notifications?unread=true").json()
    kinds = [n["kind"] for n in r["notifications"]]
    assert "plan-review-waiting" in kinds

    marked = client.post(f"/api/teams/{root.teamId}/notifications/read",
                         json={}).json()["marked"]
    assert marked == len(r["notifications"])
    assert client.get(
        f"/api/teams/{root.teamId}/notifications?unread=true"
    ).json()["notifications"] == []


def test_gate_resolution_auto_reads_its_notifications(pod, client):
    """F9: a resolved gate's unread notifications stop ringing — stale unread rows read as
    pending operator actions during the live run."""
    eng, root = pod["engine"], pod["root"]
    eng.delegate(root.id, pod["backend"]["id"], "implement")
    eng.finish_turn(root.id)  # -> plan-review gate + plan-review-waiting notification

    unread = client.get(
        f"/api/teams/{root.teamId}/notifications?unread=true"
    ).json()["notifications"]
    assert any(n["kind"] == "plan-review-waiting" for n in unread)

    gate = next(g for g in eng.store.list_gates(assignment_id=root.id, state="open")
                if g.kind == "approval")
    eng.resolve_gate(gate.id, action="approve")

    unread = client.get(
        f"/api/teams/{root.teamId}/notifications?unread=true"
    ).json()["notifications"]
    assert not any(n["kind"] == "plan-review-waiting" for n in unread)


# ------------------------------------------------- F3 / F11 / F14: liveness-aware triggers
def test_no_delta_run_suppressed_while_session_is_live(pod):
    """F3+F14: a manager wake-turn settles no-delta steps while the session is actively
    streaming — with fresh liveness reported, the no-delta trigger must NOT gate it."""
    eng = pod["engine"]
    child = _fanout_child(pod)
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "w"}])
    for i in range(5):
        eng.record_step(child.id, input_tokens=10, output_tokens=1, duration_ms=5,
                        delta_kind="none", step_id=f"st_live{i}")
    eng.report_session_health(child.id, "running")  # the adapter's heartbeat, just now

    assert eng.sweep_triggers() == []
    assert eng.store.get_assignment(child.id).state == "executing"


def test_no_delta_run_fires_once_activity_goes_quiet(pod):
    """F14's other half: the same no-delta run DOES gate once the reported activity is
    stale past the grace window — dead spinning, not mid-thought."""
    from datetime import UTC, datetime, timedelta

    from canopy_server.deps import get_db

    eng = pod["engine"]
    child = _fanout_child(pod)
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "w"}])
    for i in range(5):
        eng.record_step(child.id, input_tokens=10, output_tokens=1, duration_ms=5,
                        delta_kind="none", step_id=f"st_dead{i}")
    # Activity stale past the no-delta grace but short of the quiet-stall threshold —
    # isolates the no-delta trigger from the quiet one.
    stale = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    with get_db().transaction() as conn:
        conn.execute(
            "UPDATE work_assignment SET last_activity_at=? WHERE id=?", (stale, child.id),
        )
        conn.execute("UPDATE work_step SET created_at=? WHERE assignment_id=?",
                     (stale, child.id))

    opened = eng.sweep_triggers()
    assert any(g.assignmentId == child.id and "no-delta" in g.reason for g in opened)


def test_fresh_activity_defers_the_quiet_stall(pod):
    """F14: stale steps + fresh adapter liveness = a long-thinking session, not a stall."""
    from canopy_server.deps import get_db

    eng = pod["engine"]
    child = _fanout_child(pod)
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "w"}])
    eng.record_step(child.id, input_tokens=10, output_tokens=1, duration_ms=5,
                    delta_kind="tool-effect", step_id="st_old")
    with get_db().transaction() as conn:
        conn.execute("UPDATE work_step SET created_at=? WHERE assignment_id=?",
                     ("2020-01-01T00:00:00+00:00", child.id))
    eng.report_session_health(child.id, "running")  # stream events still flowing

    assert eng.sweep_triggers() == []


def test_erroring_session_surfaces_provider_limit_not_stall(pod):
    """F11: a session dying on a provider limit is a provider-limit notification carrying
    the cause — never a stall intervention gate."""
    eng = pod["engine"]
    child = _fanout_child(pod)
    eng.mark_intake_complete(child.id)
    eng.declare_plan(child.id, [{"title": "w"}])
    eng.report_session_health(
        child.id, "erroring",
        "You've hit your session limit - resets 12:50am (America/Los_Angeles)",
    )

    assert eng.sweep_triggers() == []  # no intervention gates opened
    assert eng.store.get_assignment(child.id).state == "executing"  # never suspended
    notes = eng.store.list_notifications(child.teamId)
    limit_notes = [n for n in notes if n.kind == "provider-limit"]
    assert len(limit_notes) == 1 and "resets 12:50am" in limit_notes[0].text
    # Idempotent across sweeps: the same failure never spams the feed.
    eng.sweep_triggers()
    assert len([n for n in eng.store.list_notifications(child.teamId)
                if n.kind == "provider-limit"]) == 1
