"""The Canopy MCP server (cli-runtime.md §4) — surface filtering, server-side re-check,
ToolEvents, and the engine paths behind the tools.

The adversarial cases are the point (testing.md rule 2): a non-manager calling a manager tool
and an ungranted artifact fetch are refused at the server AND visible in ToolEvents.
"""

from __future__ import annotations

import base64


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _rpc(client, token, method, params=None, id_=1):
    return client.post("/api/dp/mcp", headers=_h(token),
                       json={"jsonrpc": "2.0", "id": id_, "method": method,
                             "params": params or {}})


def _call(client, token, name, arguments=None):
    r = _rpc(client, token, "tools/call", {"name": name, "arguments": arguments or {}})
    assert r.status_code == 200, r.text
    return r.json()


def _node(org: dict, role_key: str) -> dict:
    return next(a for a in org["agents"] if a["role"]["key"] == role_key)


def test_initialize_and_handshake(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    s = mint_session(org["id"])
    r = _rpc(client, s["token"], "initialize")
    body = r.json()["result"]
    assert body["serverInfo"]["name"] == "canopy" and "tools" in body["capabilities"]
    assert _rpc(client, s["token"], "notifications/initialized").status_code == 202

    unauth = client.post("/api/dp/mcp", json={"jsonrpc": "2.0", "id": 1,
                                              "method": "tools/list"})
    assert unauth.status_code == 401


def test_tools_list_is_surface_filtered(client, make_org, mint_session):
    """Layer 1: the IC's world simply does not contain the manager tools."""
    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead, be = _node(org, "engineering-lead"), _node(org, "backend-engineer")
    s_lead = mint_session(org["id"], node_id=lead["id"])
    s_be = mint_session(org["id"], node_id=be["id"], actuation_id=s_lead["actuationId"])

    lead_tools = {t["name"] for t in
                  _rpc(client, s_lead["token"], "tools/list").json()["result"]["tools"]}
    be_tools = {t["name"] for t in
                _rpc(client, s_be["token"], "tools/list").json()["result"]["tools"]}
    manager_only = {"delegate", "finish_turn", "reports_status", "accept", "reject"}
    assert manager_only <= lead_tools
    assert not (manager_only & be_tools)
    assert {"get_assignment", "declare_plan", "finish", "escalate"} <= be_tools


def test_manager_tool_from_ic_is_denied_and_audited(client, make_org, mint_session):
    """Layer 2, the guarantee: a hallucinated manager tool call is a 403-class error AND a
    'denied' ToolEvent — visible, never silent."""
    from canopy_server.deps import get_work_store

    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    be = _node(org, "backend-engineer")
    s = mint_session(org["id"], node_id=be["id"])

    r = _rpc(client, s["token"], "tools/call",
             {"name": "delegate", "arguments": {"reportNodeId": "x", "brief": "y"}})
    assert "error" in r.json()

    events = get_work_store().list_tool_events(s["actuationId"], be["id"])
    assert events and events[-1]["tool"] == "delegate" and events[-1]["outcome"] == "denied"

    unknown = _rpc(client, s["token"], "tools/call", {"name": "rm_rf", "arguments": {}})
    assert "error" in unknown.json()
    events = get_work_store().list_tool_events(s["actuationId"], be["id"])
    assert events[-1]["tool"] == "rm_rf" and events[-1]["outcome"] == "denied"


def test_full_assignment_via_mcp_tools(client, make_org, mint_session):
    """The mvp E3 demo shape: a 2-node org runs delegate → work → finish → accept entirely
    through MCP tool calls (the same engine paths the loop runtime uses)."""
    from canopy_server.deps import get_engine, get_work_store

    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead, be = _node(org, "engineering-lead"), _node(org, "backend-engineer")
    s_lead = mint_session(org["id"], node_id=lead["id"])
    s_be = mint_session(org["id"], node_id=be["id"], actuation_id=s_lead["actuationId"])

    eng = get_engine()
    root = eng.submit_intent(org["id"], s_lead["actuationId"], "ship the CSV export",
                             target_node=lead["id"]).assignment
    eng.mark_intake_complete(root.id)
    eng.declare_plan(root.id, [{"title": "decompose"}])

    # The lead fans out over MCP (staged — root is checkpointed), then closes the turn.
    import json as _json

    res = _call(client, s_lead["token"], "delegate",
                {"reportNodeId": be["id"], "brief": "implement CSV",
                 "contractType": "PullRequest"})
    child = _json.loads(res["result"]["content"][0]["text"])
    assert child["state"] == "proposed"
    turn = _json.loads(_call(client, s_lead["token"], "finish_turn")
                       ["result"]["content"][0]["text"])
    assert turn["gateKind"] == "approval"
    eng.resolve_gate(turn["gateId"], action="approve")

    # The engineer drives its assignment end-to-end through MCP.
    cur = _json.loads(_call(client, s_be["token"], "get_assignment")
                      ["result"]["content"][0]["text"])
    assert cur["assignment"]["id"] == child["assignmentId"]
    eng.mark_intake_complete(child["assignmentId"])
    _call(client, s_be["token"], "declare_plan", {"stages": [{"title": "implement"}]})
    _call(client, s_be["token"], "update_stage", {"stageIdx": 0, "state": "active"})
    art = _json.loads(_call(client, s_be["token"], "produce_artifact",
                            {"name": "pr", "type": "code-patch",
                             "contentBase64": base64.b64encode(b"diff").decode()})
                      ["result"]["content"][0]["text"])
    _call(client, s_be["token"], "finish", {"refs": [art["ref"]], "summary": "PR v1"})

    # The lead (woken by the delivery) reviews via reports_status and accepts.
    reports = _json.loads(_call(client, s_lead["token"], "reports_status")
                          ["result"]["content"][0]["text"])["reports"]
    assert reports[0]["state"] == "delivering"
    _call(client, s_lead["token"], "accept", {"assignmentId": child["assignmentId"]})
    assert get_work_store().get_assignment(child["assignmentId"]).state == "closed"

    # Every call above landed a ToolEvent for its node.
    lead_events = [e["tool"] for e in
                   get_work_store().list_tool_events(s_lead["actuationId"], lead["id"])]
    assert ["delegate", "finish_turn", "reports_status", "accept"] == lead_events


def test_mcp_fetch_respects_the_grant_wall(client, make_org, mint_session):
    from canopy_server.deps import get_engine, get_work_store

    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead, be = _node(org, "engineering-lead"), _node(org, "backend-engineer")
    s_lead = mint_session(org["id"], node_id=lead["id"])
    s_be = mint_session(org["id"], node_id=be["id"], actuation_id=s_lead["actuationId"])

    eng = get_engine()
    root = eng.submit_intent(org["id"], s_lead["actuationId"], "private work",
                             target_node=lead["id"]).assignment
    eng.mark_intake_complete(root.id)
    art = eng.put_artifact(root.id, "secret", "document", b"classified")

    r = _rpc(client, s_be["token"], "tools/call",
             {"name": "fetch_artifact", "arguments": {"ref": art.ref}})
    assert "error" in r.json()  # ungranted → denied at the server

    events = get_work_store().list_tool_events(s_be["actuationId"], be["id"])
    assert events[-1]["tool"] == "fetch_artifact" and events[-1]["outcome"] == "denied"
