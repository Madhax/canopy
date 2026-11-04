"""Model Gateway via the data-plane route — the A1 demo, as tests.

Metered completion through the mock provider, the run-token gate, the hard-stop 402 *before*
dispatch, and the coordination/production step tag (risk SC-1).
"""

from __future__ import annotations


def _post(client, token, **body):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = {"messages": [{"role": "user", "content": "hello world"}]}
    payload.update(body)
    return client.post("/api/dp/llm/complete", headers=headers, json=payload)


def test_mock_completion_is_metered(client, make_org, mint_session):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    s = mint_session(team["id"], allowance=5000)
    r = _post(client, s["token"], kind="production")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "mock"
    assert body["outputTokens"] > 0
    assert body["meter"]["spent"] > 0
    assert body["stepId"].startswith("st_")
    assert body["priceKnown"] is True  # mock-1 is in the price table (free)

    roll = client.get(f"/api/teams/{team['id']}/spend?groupBy=node").json()
    assert roll["costsAreEstimates"] is True
    assert any(row["key"] == s["nodeId"] for row in roll["rows"])


def test_missing_token_is_401(client):
    assert _post(client, None).status_code == 401


def test_bad_token_is_401(client, make_org, mint_session):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    mint_session(team["id"])
    assert _post(client, "not-a-real-token").status_code == 401


def test_hard_stop_returns_402_before_dispatch(client, make_org, mint_session):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    # allowance 10 < maxOutput 4096 → the very first reservation cannot be covered.
    s = mint_session(team["id"], allowance=10, max_output=4096)
    r = _post(client, s["token"])
    assert r.status_code == 402
    assert r.json()["error"]["code"] == "BUDGET_EXHAUSTED"
    assert r.json()["error"]["meterId"] == s["meterId"]

    # Nothing was dispatched or recorded — the halt is *before* the model call.
    roll = client.get(f"/api/teams/{team['id']}/spend?groupBy=node").json()
    assert roll["rows"] == []
    feed = client.get(f"/api/teams/{team['id']}/activity").json()
    assert any(e["kind"] == "budget.hard_stop" for e in feed["events"])


def test_step_is_tagged_coordination(client, make_org, mint_session):
    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    s = mint_session(team["id"])
    r = _post(client, s["token"], kind="coordination")
    assert r.status_code == 200
    assert r.json()["kind"] == "coordination"

    from canopy_server.deps import get_db

    # E6: gateway_step is retired — work_step is THE Step record (runtimes report it with the
    # gateway's step id) and the ledger's SpendEvent is the money audit. Only the response
    # carries the tag at the gateway layer now.
    with get_db().connect() as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'gateway_step'"
        ).fetchone()
        spend = conn.execute(
            "SELECT input_tokens FROM ledger_spend_event WHERE step_id = ?",
            (r.json()["stepId"],),
        ).fetchone()
    assert table is None
    assert spend is not None


def test_gemini_provider_tool_calls_and_catalog(monkeypatch):
    """GeminiProvider maps neutral ToolSpec -> google.genai FunctionDeclaration and extracts
    function_call parts into ToolCall results with stopReason='tool_use'."""
    import asyncio
    from types import SimpleNamespace

    from canopy_server.gateway.base import CompletionRequest, Message, ToolSpec
    from canopy_server.gateway.providers import GeminiProvider

    captured: dict = {}

    class FakeModels:
        async def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            part_text = SimpleNamespace(text="Calling tool...", function_call=None)
            part_fc = SimpleNamespace(
                text=None,
                function_call=SimpleNamespace(
                    id="fc_1", name="declare_plan", args={"stages": [{"title": "s1"}]}
                ),
            )
            cand = SimpleNamespace(content=SimpleNamespace(parts=[part_text, part_fc]))
            usage = SimpleNamespace(prompt_token_count=120, candidates_token_count=35)
            return SimpleNamespace(candidates=[cand], usage_metadata=usage)

    fake_client = SimpleNamespace(aio=SimpleNamespace(models=FakeModels()))
    prov = GeminiProvider()
    monkeypatch.setattr(prov, "_client", lambda cred, endpoint: fake_client)

    req = CompletionRequest(
        system="You are an agent.",
        messages=[Message(role="user", content="plan the work")],
        tools=[
            ToolSpec(
                name="declare_plan",
                description="Declare stages",
                inputSchema={"type": "object", "properties": {"stages": {"type": "array"}}},
            )
        ],
    )
    res = asyncio.run(prov.complete(req, "fake-key", model="gemini-2.5-pro", endpoint=None))
    assert res.stopReason == "tool_use"
    assert res.text == "Calling tool..."
    assert len(res.toolCalls) == 1
    assert res.toolCalls[0].id == "fc_1"
    assert res.toolCalls[0].name == "declare_plan"
    assert res.toolCalls[0].arguments == {"stages": [{"title": "s1"}]}
    assert res.inputTokens == 120
    assert res.outputTokens == 35
    assert captured["config"].tools is not None
    decls = captured["config"].tools[0].function_declarations
    assert len(decls) == 1 and decls[0].name == "declare_plan"

    known_ids = {m.id for m in prov.list_known_models()}
    assert {
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
    } <= known_ids


def test_gateway_records_cache_tokens_in_meter_and_ledger(client, make_org, mint_session):
    """Gateway completions forward cacheReadTokens and cacheCreationTokens into the ledger
    and charge billing-weighted tokens against meter.spent."""
    from canopy_server.deps import get_db

    team = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    s = mint_session(team["id"], allowance=5000)
    r = _post(
        client,
        s["token"],
        kind="production",
        providerOptions={
            "mock": {
                "output_tokens": 50,
                "cache_read_tokens": 1000,
                "cache_creation_tokens": 200,
            }
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cacheReadTokens"] == 1000
    assert body["cacheCreationTokens"] == 200
    # Effective meter charge = inputTokens + 50 + int(1000*0.1 + 200*1.25) = inputTokens + 400
    assert body["meter"]["spent"] == body["inputTokens"] + 50 + 350

    with get_db().connect() as conn:
        spend = conn.execute(
            "SELECT cache_read_tokens, cache_creation_tokens FROM ledger_spend_event "
            "WHERE step_id = ?",
            (body["stepId"],),
        ).fetchone()
    assert spend["cache_read_tokens"] == 1000
    assert spend["cache_creation_tokens"] == 200
