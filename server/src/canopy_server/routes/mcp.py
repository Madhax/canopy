"""The Canopy MCP server (cli-runtime.md §4) — the tool plane for CLI sessions.

A streamable-HTTP MCP endpoint at ``/api/dp/mcp``: JSON-RPC 2.0 over POST, run-token
authenticated. It exposes **only** the tools the caller's charter allows (surface filtering,
envelope layer 1) and re-checks server-side per call (layer 2) — a hallucinated or filtered-out
tool call is a JSON-RPC error AND a ``denied`` ToolEvent, logged, never silent. Every call is a
thin veneer over the exact engine paths the ``loop`` runtime's dp endpoints use — one
authorization path for both runtimes.

Implements the minimal protocol surface a headless Claude Code session needs: ``initialize``,
``notifications/initialized``, ``tools/list``, ``tools/call``. Stateless by design (work truth
lives in the engine); no session ids required.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from ..deps import (
    get_actuator,
    get_engine,
    get_ledger,
    get_runtokens,
    get_work_store,
)
from ..engine.engine import WorkError

router = APIRouter(prefix="/dp")

PROTOCOL_VERSION = "2024-11-05"


# --------------------------------------------------------------------------- #
# Tool registry: name -> (description, input schema, handler, manager_only)
# Handlers receive (rec, engine, work_store, args) and return a JSON-able dict.
# --------------------------------------------------------------------------- #
def _current(work_store, rec):
    a = work_store.current_assignment(rec.actuationId, rec.nodeId)
    if a is None:
        raise WorkError("no active assignment for this node")
    return a


def _t_get_assignment(rec, engine, work_store, args) -> dict:
    a = work_store.current_assignment(rec.actuationId, rec.nodeId)
    if a is None:
        return {"assignment": None}
    brief = work_store.get_brief(a.id)
    meter = get_ledger().get_meter(a.meterId) if a.meterId else None
    return {
        "assignment": a.model_dump(),
        "brief": brief.model_dump() if brief else None,
        "contract": {"kind": a.contractKind, "type": a.contractType},
        "memory": [m.entry for m in work_store.get_memory(rec.orgId, rec.nodeId)],
        "meter": meter.model_dump() if meter else None,
        "notes": [n.model_dump() for n in work_store.take_undelivered_notes(a.id)],
    }


def _t_declare_plan(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    plan = engine.declare_plan(a.id, args["stages"])
    return {"planId": plan.id, "version": plan.version}


def _t_update_stage(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    engine.update_stage(a.id, int(args["stageIdx"]), args["state"])
    return {"ok": True}


def _t_produce_artifact(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    content = base64.b64decode(args["contentBase64"]) if "contentBase64" in args \
        else args.get("content", "").encode()
    meta = engine.put_artifact(
        a.id, args["name"], args.get("type", "document"), content,
        filename=args.get("filename"),
    )
    return {"ref": meta.ref, "version": meta.version}


def _t_fetch_artifact(rec, engine, work_store, args) -> dict:
    ref = args["ref"]
    meta = engine.artifacts.resolve(ref)
    if meta is None or meta.orgId != rec.orgId:
        raise WorkError(f"no artifact {ref}")
    if meta.nodeId != rec.nodeId and ref not in work_store.refs_granted_to(
        rec.actuationId, rec.nodeId
    ):
        raise _GrantDenied(f"ref {ref} is not in the caller's granted set")
    content = engine.artifacts.read(ref)
    return {"meta": meta.model_dump(),
            "contentBase64": base64.b64encode(content).decode() if content else None}


def _t_open_clarification(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    gate = engine.open_clarification(a.id, args["question"])
    return {"gateId": gate.id, "state": "gated"}


def _t_escalate(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    gate = engine.open_escalation(a.id, args["question"], refs=args.get("refs"))
    return {"gateId": gate.id, "state": "gated"}


def _t_finish(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    deliverable = engine.finish(
        a.id, artifact_refs=args.get("refs", []), summary=args.get("summary", ""),
        kind=args.get("kind"), attestation=args.get("attestation"),
    )
    return {"deliverableId": deliverable.id, "refs": deliverable.artifactRefs}


def _t_delegate(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    child = engine.delegate(
        a.id, args["reportNodeId"], args["brief"], refs=args.get("refs"),
        contract_kind=args.get("contractKind"), contract_type=args.get("contractType"),
        depends_on=[
            d if isinstance(d, dict) else {"assignmentId": d}
            for d in args.get("dependsOn", [])
        ],
    )
    return {"assignmentId": child.id, "state": child.state}


def _t_finish_turn(rec, engine, work_store, args) -> dict:
    a = _current(work_store, rec)
    gate = engine.finish_turn(a.id)
    return {"gateId": gate.id if gate else None,
            "gateKind": gate.kind if gate else None}


def _t_reports_status(rec, engine, work_store, args) -> dict:
    """R1: subtree telemetry — the manager's own children with states, cursors, meters, and
    open gates (sub-org-opaque; one level is the MVP scope)."""
    a = _current(work_store, rec)
    out = []
    for c in work_store.list_children(a.id):
        plan = work_store.get_plan(c.id)
        cursor = next((s.idx for s in plan.stages if s.state == "active"), None) if plan else None
        meter = get_ledger().get_meter(c.meterId) if c.meterId else None
        gates = work_store.list_gates(assignment_id=c.id, state="open")
        out.append({
            "assignmentId": c.id, "nodeId": c.nodeId, "state": c.state,
            "planCursor": cursor,
            "meter": {"spent": meter.spent, "allowance": meter.allowance} if meter else None,
            "openGates": [g.kind for g in gates],
        })
    return {"reports": out}


def _t_accept(rec, engine, work_store, args) -> dict:
    a = engine.accept(args["assignmentId"], note=args.get("note"))
    return {"assignmentId": a.id, "state": a.state}


def _t_reject(rec, engine, work_store, args) -> dict:
    a = engine.reject(
        args["assignmentId"], args.get("note", ""), revised_brief=args.get("revisedBrief"),
    )
    return {"assignmentId": a.id, "state": a.state}


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


_STR = {"type": "string"}
_STAGES = {"type": "array", "items": _obj({"title": _STR, "completion": _STR,
                                           "sizing": _STR}, ["title"])}
_REFS = {"type": "array", "items": _STR}

TOOLS: dict[str, dict[str, Any]] = {
    # ---- baseline (every agent) ----
    "get_assignment": {
        "description": "Your current assignment: brief, contract, meter, memory, notes.",
        "schema": _obj({}, []), "handler": _t_get_assignment, "manager": False,
    },
    "declare_plan": {
        "description": "Declare (or revise) your plan as observable stages before working.",
        "schema": _obj({"stages": _STAGES}, ["stages"]),
        "handler": _t_declare_plan, "manager": False,
    },
    "update_stage": {
        "description": "Advance your plan cursor: set a stage active/done/dropped.",
        "schema": _obj({"stageIdx": {"type": "integer"},
                        "state": {"type": "string",
                                  "enum": ["pending", "active", "done", "dropped"]}},
                       ["stageIdx", "state"]),
        "handler": _t_update_stage, "manager": False,
    },
    "produce_artifact": {
        "description": "Store an output in the Artifact Store; returns the org:// ref your "
                       "deliverable must cite.",
        "schema": _obj({"name": _STR, "type": _STR, "content": _STR,
                        "contentBase64": _STR, "filename": _STR}, ["name"]),
        "handler": _t_produce_artifact, "manager": False,
    },
    "fetch_artifact": {
        "description": "Fetch an artifact you produced or were granted via your brief.",
        "schema": _obj({"ref": _STR}, ["ref"]),
        "handler": _t_fetch_artifact, "manager": False,
    },
    "open_clarification": {
        "description": "The brief is defective — suspend and ask the issuer. Do not guess.",
        "schema": _obj({"question": _STR}, ["question"]),
        "handler": _t_open_clarification, "manager": False,
    },
    "escalate": {
        "description": "Ask a decision above your pay grade; the answer arrives on resume.",
        "schema": _obj({"question": _STR, "refs": _REFS}, ["question"]),
        "handler": _t_escalate, "manager": False,
    },
    "finish": {
        "description": "Submit your deliverable (refs + summary) and end the assignment turn.",
        "schema": _obj({"refs": _REFS, "summary": _STR}, []),
        "handler": _t_finish, "manager": False,
    },
    # ---- managers only (charter has reports) ----
    "delegate": {
        "description": "Create a child assignment on one of your direct reports.",
        "schema": _obj({"reportNodeId": _STR, "brief": _STR, "refs": _REFS,
                        "contractKind": _STR, "contractType": _STR,
                        "dependsOn": {"type": "array"}}, ["reportNodeId", "brief"]),
        "handler": _t_delegate, "manager": True,
    },
    "finish_turn": {
        "description": "End your fan-out turn: submits the proposed batch for review, or "
                       "re-enters the await gate while children remain.",
        "schema": _obj({}, []), "handler": _t_finish_turn, "manager": True,
    },
    "reports_status": {
        "description": "Your reports' live telemetry: states, plan cursors, meters, gates.",
        "schema": _obj({}, []), "handler": _t_reports_status, "manager": True,
    },
    "accept": {
        "description": "Accept a report's deliverable — the final verdict, after verification.",
        "schema": _obj({"assignmentId": _STR, "note": _STR}, ["assignmentId"]),
        "handler": _t_accept, "manager": True,
    },
    "reject": {
        "description": "Reject a report's deliverable with a note; optionally revise the brief "
                       "(rework funding follows the brief version).",
        "schema": _obj({"assignmentId": _STR, "note": _STR, "revisedBrief": _STR},
                       ["assignmentId", "note"]),
        "handler": _t_reject, "manager": True,
    },
}


class _GrantDenied(Exception):
    pass


def _is_manager(actuator, engine, rec) -> bool:
    """Manager tools appear iff the charter (or, pre-charter, the chart itself) gives the node
    reports — the same data the router enforces channels with (invariant 4)."""
    charter = actuator.get_charter(rec.actuationId, rec.nodeId)
    if charter is not None:
        return bool(charter.get("reportNodeIds"))
    try:
        org = engine.orgs.read(rec.orgId)
    except Exception:  # noqa: BLE001 - no org doc => no reports
        return False
    return any(a.managerId == rec.nodeId for a in org.agents)


def _visible_tools(actuator, engine, rec) -> dict[str, dict[str, Any]]:
    manager = _is_manager(actuator, engine, rec)
    return {name: t for name, t in TOOLS.items() if manager or not t["manager"]}


def _rpc_error(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _rpc_result(id_: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _params_hash(args: dict) -> str:
    return hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]


@router.post("/mcp")
def mcp_endpoint(
    body: dict,
    authorization: str | None = Header(default=None),
    runtokens=Depends(get_runtokens),
    actuator=Depends(get_actuator),
    engine=Depends(get_engine),
    work_store=Depends(get_work_store),
) -> Any:
    token = None
    if authorization:
        parts = authorization.split(" ", 1)
        token = parts[1].strip() if len(parts) == 2 else authorization.strip()
    rec = runtokens.resolve(token) if token else None
    if rec is None:
        return JSONResponse(status_code=401, content={"error": {
            "code": "RUN_TOKEN_INVALID", "message": "unknown or missing run token"}})

    method = body.get("method", "")
    id_ = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return _rpc_result(id_, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "canopy", "version": "1.0.0"},
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return JSONResponse(status_code=202, content=None)
    if method == "ping":
        return _rpc_result(id_, {})

    if method == "tools/list":
        tools = [
            {"name": name, "description": t["description"], "inputSchema": t["schema"]}
            for name, t in _visible_tools(actuator, engine, rec).items()
        ]
        return _rpc_result(id_, {"tools": tools})

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        cur = work_store.current_assignment(rec.actuationId, rec.nodeId)
        aid = cur.id if cur else None
        tool = TOOLS.get(name)
        # Layer 2, the guarantee: re-check per call. Unknown tool or a manager tool from a
        # non-manager is a denial — recorded, never silent (envelope §3.3).
        if tool is None or (tool["manager"] and not _is_manager(actuator, engine, rec)):
            work_store.record_tool_event(
                org_id=rec.orgId, actuation_id=rec.actuationId, node_id=rec.nodeId,
                assignment_id=aid, tool=name, params_hash=_params_hash(args),
                outcome="denied", detail="tool not in the caller's surface",
            )
            return _rpc_error(id_, -32602, f"tool {name!r} is not available to this agent")
        try:
            result = tool["handler"](rec, engine, work_store, args)
            outcome, detail = "ok", ""
        except _GrantDenied as exc:
            outcome, detail = "denied", str(exc)
            result = None
        except WorkError as exc:
            outcome, detail = "error", str(exc)
            result = None
        work_store.record_tool_event(
            org_id=rec.orgId, actuation_id=rec.actuationId, node_id=rec.nodeId,
            assignment_id=aid, tool=name, params_hash=_params_hash(args),
            outcome=outcome, detail=detail,
        )
        if outcome == "denied":
            return _rpc_error(id_, -32602, detail)
        if outcome == "error":
            return _rpc_result(id_, {
                "content": [{"type": "text", "text": f"error: {detail}"}], "isError": True,
            })
        return _rpc_result(id_, {
            "content": [{"type": "text", "text": json.dumps(result)}], "isError": False,
        })

    return _rpc_error(id_, -32601, f"method {method!r} not supported")
