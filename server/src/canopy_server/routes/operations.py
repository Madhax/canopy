"""Operator observability: spend rollups and the activity feed (control-plane.md §9).

The full burn UI is A5; these endpoints exist now because the ledger and activity log are built in
A1 and the rollup is the honest answer to "what did this cost" — drillable node/task/model. Costs
are labeled estimates (risk IM-5); token counts are provider-authoritative.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..deps import get_activity, get_ledger

router = APIRouter()


@router.get("/organizations/{org_id}/spend")
def spend_rollup(
    org_id: str,
    groupBy: Literal["node", "task", "model", "intent", "assignment"] = "node",
    split: bool = False,
    ledger=Depends(get_ledger),
) -> Any:
    """The cost explorer's feed (engine.md §6, extends not mutates): the A1 rollups plus the
    E5 work-layer dimensions — by intent / by assignment — and `split=true` adds the
    coordination-vs-production split (SC-1) from the unified Step's kind."""
    if groupBy in ("intent", "assignment") or split:
        from ..deps import get_db

        dim = ("COALESCE(a.intent_id, 'unattributed')" if groupBy == "intent"
               else "COALESCE(e.task_id, 'unattributed')" if groupBy == "assignment"
               else {"node": "e.node_id", "task": "e.task_id", "model": "e.model"}[groupBy])
        split_cols = (", SUM(CASE WHEN COALESCE(ws.kind,'production')='coordination' "
                      "THEN e.input_tokens+e.output_tokens ELSE 0 END) AS coordination_tokens"
                      ", SUM(CASE WHEN COALESCE(ws.kind,'production')!='coordination' "
                      "THEN e.input_tokens+e.output_tokens ELSE 0 END) AS production_tokens"
                      if split else "")
        with get_db().connect() as conn:
            rows = conn.execute(
                f"SELECT {dim} AS key, SUM(e.input_tokens) AS input_tokens, "  # noqa: S608
                "SUM(e.output_tokens) AS output_tokens, "
                "SUM(e.cache_read_tokens) AS cache_read_tokens, "
                "SUM(e.cache_creation_tokens) AS cache_creation_tokens, "
                "SUM(e.est_cost_micros) AS est_cost_micros, COUNT(*) AS steps"
                f"{split_cols} "
                "FROM ledger_spend_event e "
                "LEFT JOIN work_assignment a ON a.id = e.task_id "
                "LEFT JOIN work_step ws ON ws.id = e.step_id "
                "WHERE e.org_id = ? GROUP BY key ORDER BY est_cost_micros DESC",
                (org_id,),
            ).fetchall()
        return {"groupBy": groupBy, "split": split, "costsAreEstimates": True,
                "rows": [dict(r) for r in rows]}
    return {
        "groupBy": groupBy,
        "costsAreEstimates": True,
        "rows": ledger.rollup(org_id, groupBy),
    }


#: Assignment states the node has accepted but not begun — mission control's queue depth.
_QUEUED_STATES = frozenset({"created", "briefed"})


@router.get("/organizations/{org_id}/pulse")
def org_pulse(org_id: str, windowMinutes: int = 10, ledger=Depends(get_ledger)) -> Any:
    """Mission control's feed (operator-experience.md §2): the org pulse header (actuation
    state · open intents · burn rate · open gates by kind · attention count) plus one overlay
    row per node (status, current assignment, queue/WIP, meter, gate kinds, runtime kind).
    One aggregate, so the live chart is a projection with zero client-side joins."""
    from ..catalog import get_catalog
    from ..config import get_runtime_override
    from ..deps import get_actuator, get_db, get_directory, get_store, get_work_store
    from ..engine.models import ASSIGNMENT_ACTIVE_STATES

    store, work_store = get_store(), get_work_store()
    if not store.exists(org_id):
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": f"No organization {org_id!r}"}},
        )
    org = store.read(org_id)
    current_view = get_actuator().get_current(org_id)

    # Node status: the live directory wins (idle/engaged/gated/dead moves with heartbeats);
    # the actuation node row is the fallback while provisioning; else the org isn't actuated.
    status_by_node: dict[str, str] = {}
    if current_view:
        for n in current_view.nodes:
            status_by_node[n.nodeId] = n.status or n.subState
        if current_view.state in ("live", "degraded"):
            for d in get_directory().list(current_view.id):
                status_by_node[d.nodeId] = d.status

    intents = work_store.list_intents(org_id)
    assignments = work_store.list_assignments(org_id=org_id)
    node_of_assignment = {a.id: a.nodeId for a in assignments}
    open_gates = work_store.list_gates(org_id=org_id, state="open")
    gate_kinds_by_node: dict[str, list[str]] = {}
    # F5: kind alone can't tell operator work from internal wiring (a dependency gate is the
    # org running normally) — carry the owner so the UI can tone them apart.
    gates_by_node: dict[str, list[dict]] = {}
    for g in open_gates:
        node = node_of_assignment.get(g.assignmentId)
        if node is not None:
            gate_kinds_by_node.setdefault(node, []).append(g.kind)
            gates_by_node.setdefault(node, []).append({"kind": g.kind, "owner": g.owner})

    # Burn: spend inside the trailing window, expressed per-minute / per-hour (estimates, IM-5).
    window = max(1, min(windowMinutes, 24 * 60))
    cutoff = (
        (datetime.now(UTC) - timedelta(minutes=window)).isoformat().replace("+00:00", "Z")
    )
    with get_db().connect() as conn:
        burn_row = conn.execute(
            "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens, "
            "COALESCE(SUM(est_cost_micros), 0) AS micros "
            "FROM ledger_spend_event WHERE org_id = ? AND created_at >= ?",
            (org_id, cutoff),
        ).fetchone()

    runtime_override = get_runtime_override()
    catalog = get_catalog()
    role_runtime = {r.key: getattr(r, "defaultRuntime", "loop") or "loop" for r in catalog.roles}

    by_node: dict[str, list] = {}
    for a in assignments:
        by_node.setdefault(a.nodeId, []).append(a)

    nodes = []
    for agent in org.agents:
        mine = by_node.get(agent.id, [])
        active = [a for a in mine if a.state in ASSIGNMENT_ACTIVE_STATES]
        current = next((a for a in active if a.state not in _QUEUED_STATES), None)
        meter = ledger.get_meter(current.meterId) if current and current.meterId else None
        brief = work_store.get_brief(current.id) if current else None
        # F15: stage progress is the honest per-assignment headline (the meter arc read as
        # progress and sat at ~0% all run) — completed stages over the living plan's stages.
        plan = work_store.get_plan(current.id) if current else None
        stage_progress = (
            {"done": sum(1 for s in plan.stages if s.state == "done"),
             "total": len(plan.stages)}
            if plan and plan.stages else None
        )
        nodes.append({
            "nodeId": agent.id,
            "name": agent.name,
            "managerId": agent.managerId,
            "roleKey": agent.role.key,
            "status": status_by_node.get(agent.id, "not-actuated"),
            "current": (
                {"assignmentId": current.id, "state": current.state,
                 "briefPreview": (brief.text[:80] if brief else ""),
                 "stageProgress": stage_progress}
                if current else None
            ),
            "queueDepth": sum(1 for a in active if a.state in _QUEUED_STATES),
            "wip": len(active),
            "meter": (
                {"spent": meter.spent, "allowance": meter.allowance, "warned": meter.warned,
                 "state": meter.state}
                if meter else None
            ),
            "openGateKinds": gate_kinds_by_node.get(agent.id, []),
            "openGates": gates_by_node.get(agent.id, []),
            "runtimeKind": runtime_override or role_runtime.get(agent.role.key, "loop"),
        })

    return {
        "actuation": (
            {"id": current_view.id, "state": current_view.state} if current_view else None
        ),
        "intents": {
            "open": sum(1 for i in intents if i.state == "open"),
            "total": len(intents),
        },
        "gates": {
            "open": len(open_gates),
            "byKind": dict(Counter(g.kind for g in open_gates)),
            "attention": sum(1 for g in open_gates if g.owner == "operator"),
        },
        "burn": {
            "windowMinutes": window,
            "tokensPerMinute": burn_row["tokens"] / window,
            "estCostMicrosPerHour": burn_row["micros"] * 60 / window,
            "costsAreEstimates": True,
        },
        "nodes": nodes,
    }


@router.get("/organizations/{org_id}/activity")
def activity_feed(
    org_id: str, after: int = 0, limit: int = 100, activity=Depends(get_activity)
) -> Any:
    limit = max(1, min(limit, 500))
    events = activity.list(org_id, after_seq=after, limit=limit)
    next_cursor = events[-1]["seq"] if events else after
    return JSONResponse(content={"events": events, "nextCursor": next_cursor})
