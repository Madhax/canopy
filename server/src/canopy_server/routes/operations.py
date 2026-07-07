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
    groupBy: Literal["node", "task", "model"] = "node",
    ledger=Depends(get_ledger),
) -> Any:
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
