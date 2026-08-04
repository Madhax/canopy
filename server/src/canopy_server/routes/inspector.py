"""Agent inspector — the operator's per-node introspection surface (engine.md §6,
operator-experience.md §3: "introspect the state of any one agent").

One aggregate (`GET /organizations/{id}/agents/{nodeId}/state`) feeds the eight-tab panel;
memory get/reset and the workspace file preview are the only extra endpoints. Everything is
read-only except the memory reset (the "backfill the position" act — audited). Workspace
inspection honors invariant 2's spirit: the platform and its operator can look, no agent can.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..catalog import get_catalog
from ..charter import compile_charter
from ..config import get_data_dir, get_runtime_override
from ..deps import (
    get_activity,
    get_actuator,
    get_db,
    get_directory,
    get_ledger,
    get_profile_store,
    get_store,
    get_work_store,
)
from ..engine.models import ASSIGNMENT_ACTIVE_STATES, ASSIGNMENT_TERMINAL_STATES
from .work import _assignment_detail

router = APIRouter()

#: Queue = funded work the node has not begun; anything else active is "the current one".
_QUEUED_STATES = frozenset({"created", "briefed"})

_HISTORY_LIMIT = 20
_TOOL_EVENT_LIMIT = 50
_LOG_TAIL_BYTES = 64 * 1024
_LOG_TAIL_LINES = 200
_WORKSPACE_FILE_LIMIT = 500
_PREVIEW_LIMIT = 256 * 1024  # operator-experience.md §3: text preview ≤ 256 KB


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _find_node(org, node_id: str):
    from ..actuator import enumerate_nodes

    for org_path, agent in enumerate_nodes(org):
        if agent.id == node_id:
            return org_path, agent
    return None


def _age_seconds(iso_ts: str | None) -> int | None:
    if not iso_ts:
        return None
    try:
        then = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((datetime.now(UTC) - then).total_seconds()))


def _node_root(actuation_id: str, node_id: str) -> Path:
    return get_data_dir() / "sandboxes" / actuation_id / node_id


def _list_workspace(actuation_id: str, node_id: str) -> dict[str, Any] | None:
    """Read-only file listing of the node's sandbox workspace (rel path, size, mtime)."""
    root = _node_root(actuation_id, node_id) / "workspace"
    if not root.is_dir():
        return None
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if len(files) >= _WORKSPACE_FILE_LIMIT:
            return {"root": str(root), "files": files, "truncated": True}
        st = p.stat()
        files.append({
            "path": p.relative_to(root).as_posix(),
            "size": st.st_size,
            "modifiedAt": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
        })
    return {"root": str(root), "files": files, "truncated": False}


def _log_tail(actuation_id: str, node_id: str) -> list[str]:
    """The node's subprocess log, last ~200 lines — the Session tab's raw feed."""
    log = _node_root(actuation_id, node_id) / "logs" / f"{node_id}.log"
    if not log.is_file():
        return []
    with log.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - _LOG_TAIL_BYTES))
        text = f.read().decode("utf-8", errors="replace")
    return text.splitlines()[-_LOG_TAIL_LINES:]


@router.get("/organizations/{org_id}/agents/{node_id}/state")
def agent_state(
    org_id: str,
    node_id: str,
    store=Depends(get_store),
    work_store=Depends(get_work_store),
    ledger=Depends(get_ledger),
    profiles=Depends(get_profile_store),
    actuator=Depends(get_actuator),
    directory=Depends(get_directory),
) -> Any:
    if not store.exists(org_id):
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    org = store.read(org_id)
    found = _find_node(org, node_id)
    if found is None:
        return _error(404, "NOT_FOUND", f"No agent {node_id!r} in organization {org_id!r}")
    org_path, agent = found

    # ---- Overview: charter (compiled fresh from the current doc), binding, live status
    binding = profiles.get_binding_for_node(org_id, node_id, org_path)
    profile = profiles.get_profile(binding.profileId) if binding else None
    current_view = actuator.get_current(org_id)
    actuation_id = current_view.id if current_view else None
    charter = compile_charter(
        org, org_path, node_id, catalog=get_catalog(), actuation_id=actuation_id or "",
        profile_preamble=profile.systemPreamble if profile else "",
    )
    runtime_kind = get_runtime_override() or (charter.defaultRuntime if charter else "loop")
    dir_entry = (
        directory.get(actuation_id, node_id)
        if current_view and current_view.state in ("live", "degraded")
        else None
    )

    # ---- Assignments: current / queue / history
    assignments = sorted(
        work_store.list_assignments(org_id=org_id, node_id=node_id),
        key=lambda a: a.createdAt, reverse=True,
    )
    active = [a for a in assignments if a.state in ASSIGNMENT_ACTIVE_STATES]
    current = next((a for a in active if a.state not in _QUEUED_STATES), None)
    queue = sorted(
        (a for a in active if a is not current),
        key=lambda a: (-a.priority, a.createdAt),
    )
    terminal = [a for a in assignments if a.state in ASSIGNMENT_TERMINAL_STATES]

    # ---- Spend: node totals, share of org, per-assignment (history sparkline)
    with get_db().connect() as conn:
        node_row = conn.execute(
            "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens "
            "FROM ledger_spend_event WHERE org_id = ? AND node_id = ?",
            (org_id, node_id),
        ).fetchone()
        org_row = conn.execute(
            "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens "
            "FROM ledger_spend_event WHERE org_id = ?",
            (org_id,),
        ).fetchone()
        per_assignment = {
            r["task_id"]: r["tokens"]
            for r in conn.execute(
                "SELECT task_id, SUM(input_tokens + output_tokens) AS tokens "
                "FROM ledger_spend_event WHERE org_id = ? AND node_id = ? AND task_id IS NOT "
                "NULL GROUP BY task_id",
                (org_id, node_id),
            ).fetchall()
        }
    node_tokens, org_tokens = node_row["tokens"], org_row["tokens"]

    # ---- Lifetime stats (acceptance = accepted-or-closed over terminal; escalations raised)
    gates = work_store.list_gates_for_node(org_id, node_id)
    accepted = sum(1 for a in terminal if a.state in ("accepted", "closed"))
    stats = {
        "assignmentsTotal": len(assignments),
        "assignmentsDone": len(terminal),
        "accepted": accepted,
        "acceptanceRate": (accepted / len(terminal)) if terminal else None,
        "avgCostTokens": (node_tokens // len(terminal)) if terminal else None,
        "escalations": sum(1 for g in gates if g.kind == "escalation" and g.openedBy == node_id),
    }

    # ---- Session: resume ref, tool events, subprocess log tail (best actuation we know of)
    session_ref = next((a.sessionRef for a in assignments if a.sessionRef), None)
    session_actuation = actuation_id or (assignments[0].actuationId if assignments else None)
    tool_events = (
        work_store.list_tool_events(session_actuation, node_id)[-_TOOL_EVENT_LIMIT:]
        if session_actuation else []
    )

    return {
        "nodeId": node_id,
        "orgPath": org_path,
        "charter": charter.model_dump() if charter else None,
        "binding": (
            {"profileId": profile.id, "name": profile.name, "provider": profile.provider,
             "model": profile.model}
            if profile else None
        ),
        "envelope": {
            "toolGrants": charter.toolGrants if charter else [],
            "runtimeKind": runtime_kind,
        },
        "salary": agent.salary.model_dump(),
        "directory": (
            {"status": dir_entry.status, "lastHeartbeatAt": dir_entry.lastHeartbeatAt,
             "heartbeatAgeSeconds": _age_seconds(dir_entry.lastHeartbeatAt),
             "endpointUrl": dir_entry.endpointUrl}
            if dir_entry else None
        ),
        "actuation": (
            {"id": current_view.id, "state": current_view.state} if current_view else None
        ),
        "stats": stats,
        "current": _assignment_detail(work_store, ledger, current) if current else None,
        "queue": [a.model_dump() for a in queue],
        "history": [
            {**a.model_dump(), "spentTokens": per_assignment.get(a.id, 0)}
            for a in terminal[:_HISTORY_LIMIT]
        ],
        "gates": {
            "open": [g.model_dump() for g in gates if g.state == "open"],
            "recent": [g.model_dump() for g in gates if g.state != "open"][:_HISTORY_LIMIT],
        },
        "spend": {
            "nodeTokens": node_tokens,
            "orgTokens": org_tokens,
            "sharePct": (100.0 * node_tokens / org_tokens) if org_tokens else 0.0,
        },
        "memory": [m.model_dump() for m in work_store.get_memory(org_id, node_id, limit=50)],
        "session": {
            "sessionRef": session_ref,
            "toolEvents": tool_events,
            "logTail": _log_tail(session_actuation, node_id) if session_actuation else [],
        },
        "workspace": (
            _list_workspace(session_actuation, node_id) if session_actuation else None
        ),
    }


@router.get("/organizations/{org_id}/agents/{node_id}/memory")
def get_node_memory(
    org_id: str, node_id: str, limit: int = 50, work_store=Depends(get_work_store),
) -> Any:
    limit = max(1, min(limit, 200))
    return {"entries": [m.model_dump() for m in work_store.get_memory(org_id, node_id, limit)]}


@router.delete("/organizations/{org_id}/agents/{node_id}/memory")
def reset_node_memory(
    org_id: str, node_id: str,
    work_store=Depends(get_work_store), activity=Depends(get_activity),
) -> Any:
    """The "backfill the position" act (operator-experience.md §3): wipe the node's durable
    memory. Confirm-gating is the UI's job; the audit trail is ours."""
    work_store.reset_memory(org_id, node_id)
    activity.log("operator", "memory.reset", org_id=org_id, subject_ids=[node_id])
    return {"reset": True}


@router.get("/organizations/{org_id}/agents/{node_id}/workspace/file")
def workspace_file(
    org_id: str, node_id: str, path: str,
    actuator=Depends(get_actuator), work_store=Depends(get_work_store),
) -> Any:
    """Text preview of one workspace file (≤ 256 KB). Path is relative to the node's
    workspace root; anything escaping it is rejected."""
    current_view = actuator.get_current(org_id)
    actuation_id = current_view.id if current_view else None
    if actuation_id is None:
        assignments = work_store.list_assignments(org_id=org_id, node_id=node_id)
        actuation_id = assignments[0].actuationId if assignments else None
    if actuation_id is None:
        return _error(404, "NOT_FOUND", "No workspace for this node")
    root = (_node_root(actuation_id, node_id) / "workspace").resolve()
    target = (root / path).resolve()
    if root not in target.parents and target != root:
        return _error(422, "BAD_PATH", "Path escapes the workspace")
    if not target.is_file():
        return _error(404, "NOT_FOUND", f"No file {path!r} in the workspace")
    st = target.stat()
    meta: dict[str, Any] = {
        "path": path,
        "size": st.st_size,
        "modifiedAt": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
    }
    if st.st_size > _PREVIEW_LIMIT:
        return {**meta, "content": None, "reason": "too-large"}
    raw = target.read_bytes()
    if b"\x00" in raw[:8192]:
        return {**meta, "content": None, "reason": "binary"}
    return {**meta, "content": raw.decode("utf-8", errors="replace"), "reason": None}
