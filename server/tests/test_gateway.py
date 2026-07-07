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
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    s = mint_session(org["id"], allowance=5000)
    r = _post(client, s["token"], kind="production")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "mock"
    assert body["outputTokens"] > 0
    assert body["meter"]["spent"] > 0
    assert body["stepId"].startswith("st_")
    assert body["priceKnown"] is True  # mock-1 is in the price table (free)

    roll = client.get(f"/api/organizations/{org['id']}/spend?groupBy=node").json()
    assert roll["costsAreEstimates"] is True
    assert any(row["key"] == s["nodeId"] for row in roll["rows"])


def test_missing_token_is_401(client):
    assert _post(client, None).status_code == 401


def test_bad_token_is_401(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    mint_session(org["id"])
    assert _post(client, "not-a-real-token").status_code == 401


def test_hard_stop_returns_402_before_dispatch(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    # allowance 10 < maxOutput 4096 → the very first reservation cannot be covered.
    s = mint_session(org["id"], allowance=10, max_output=4096)
    r = _post(client, s["token"])
    assert r.status_code == 402
    assert r.json()["error"]["code"] == "BUDGET_EXHAUSTED"
    assert r.json()["error"]["meterId"] == s["meterId"]

    # Nothing was dispatched or recorded — the halt is *before* the model call.
    roll = client.get(f"/api/organizations/{org['id']}/spend?groupBy=node").json()
    assert roll["rows"] == []
    feed = client.get(f"/api/organizations/{org['id']}/activity").json()
    assert any(e["kind"] == "budget.hard_stop" for e in feed["events"])


def test_step_is_tagged_coordination(client, make_org, mint_session):
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    s = mint_session(org["id"])
    r = _post(client, s["token"], kind="coordination")
    assert r.status_code == 200
    assert r.json()["kind"] == "coordination"

    from canopy_server.deps import get_db

    with get_db().connect() as conn:
        row = conn.execute(
            "SELECT kind FROM gateway_step WHERE id = ?", (r.json()["stepId"],)
        ).fetchone()
    assert row["kind"] == "coordination"
