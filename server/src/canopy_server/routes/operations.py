"""Operator observability: spend rollups and the activity feed (control-plane.md §9).

The full burn UI is A5; these endpoints exist now because the ledger and activity log are built in
A1 and the rollup is the honest answer to "what did this cost" — drillable node/task/model. Costs
are labeled estimates (risk IM-5); token counts are provider-authoritative.
"""

from __future__ import annotations

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


@router.get("/organizations/{org_id}/activity")
def activity_feed(
    org_id: str, after: int = 0, limit: int = 100, activity=Depends(get_activity)
) -> Any:
    limit = max(1, min(limit, 500))
    events = activity.list(org_id, after_seq=after, limit=limit)
    next_cursor = events[-1]["seq"] if events else after
    return JSONResponse(content={"events": events, "nextCursor": next_cursor})
