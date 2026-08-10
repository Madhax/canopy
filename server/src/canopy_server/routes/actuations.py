"""Actuation lifecycle — the operator-facing Actuate / Deactuate API (control-plane.md §9).

``POST`` validates readiness then provisions in the background (returns 202 immediately; the UI
polls ``current``). ``DELETE`` tears down. Chart edits while an actuation is live are rejected by
the phase-1 ``PUT`` (see teams route) — deactuate, edit, re-actuate (v1).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..actuator import ActuationError
from ..deps import get_actuator, get_store

router = APIRouter()


def _error(status: int, code: str, message: str, issues: list[dict] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if issues is not None:
        body["error"]["issues"] = issues
    return JSONResponse(status_code=status, content=body)


@router.post("/teams/{team_id}/actuations", status_code=202)
async def actuate(team_id: str, actuator=Depends(get_actuator), store=Depends(get_store)) -> Any:
    if not store.exists(team_id):
        return _error(404, "NOT_FOUND", f"No team {team_id!r}")
    try:
        actuation_id = actuator.create_actuation(team_id)
    except ActuationError as exc:
        return _error(
            422, "ACTUATION_BLOCKED", "Fix readiness issues before actuating.",
            [i.to_dict() for i in exc.issues],
        )
    # Provision in the background; the client polls actuations/current for per-node status.
    asyncio.create_task(actuator.provision(actuation_id))  # noqa: RUF006
    return JSONResponse(status_code=202, content={"actuationId": actuation_id,
                                                  "state": "provisioning"})


@router.get("/teams/{team_id}/actuations/current")
def current(team_id: str, actuator=Depends(get_actuator)) -> Any:
    view = actuator.get_current(team_id)
    return JSONResponse(content=view.model_dump() if view else None)


@router.delete("/teams/{team_id}/actuations/current")
async def deactuate(team_id: str, actuator=Depends(get_actuator)) -> Any:
    view = actuator.get_current(team_id)
    if view is None:
        return _error(404, "NOT_FOUND", "No active actuation to deactuate.")
    await actuator.deactuate(view.id)
    return {"actuationId": view.id, "state": "stopped"}
