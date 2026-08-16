"""The ONE marked live smoke (docs/testing.md §6; design/organizations/07 §6, C7).

Everything else in this suite runs keyless on `mock` + the fake CLI. This file is the single
exception: a real, logged-in `claude` drives one tiny session through the cli-claude adapter
and the MCP server over real HTTP, and the assertion is the capacity layer's done-bar — a
**tier-2 (provider-event) reading lands** on the operator's subscription account, and the
console aggregate shows it with source + age. It also confirms the money path metered the
session (settled steps on the assignment).

It is skipped unless BOTH hold:

- ``CANOPY_LIVE=1`` in the environment (explicit opt-in — this spends subscription quota);
- ``claude`` resolves on PATH (or ``CANOPY_CLI_CMD`` names it).

Run it by hand, once per release checklist::

    CANOPY_LIVE=1 uv run pytest -m live -q          # PowerShell: $env:CANOPY_LIVE='1'

Knobs: ``CANOPY_LIVE_MODEL`` (default ``claude-haiku-4-5``, the cheapest tier), and the
adapter's own ``CANOPY_MAX_TURNS`` (pinned to 4 here). Never wire this into CI.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

_AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))

from canopy_agent import cli_runtime  # noqa: E402

from test_cli_runtime import _agent, _cfg, _node, _seed_charter, _wait_session_done  # noqa: E402

pytestmark = pytest.mark.live


def _claude_on_path() -> bool:
    override = os.environ.get("CANOPY_CLI_CMD")
    if override:
        return True
    return shutil.which("claude") is not None


@pytest.mark.skipif(os.environ.get("CANOPY_LIVE") != "1",
                    reason="live smoke: opt in with CANOPY_LIVE=1 (spends real quota)")
@pytest.mark.skipif(not _claude_on_path(), reason="live smoke: no `claude` on PATH")
def test_live_max_login_lands_a_tier2_reading(
    client, make_org, mint_session, live_server, tmp_path, monkeypatch,
):
    from canopy_server.deps import (
        get_capacity_ledger,
        get_db,
        get_engine,
        get_provider_accounts,
    )

    monkeypatch.setenv("CANOPY_CAPACITY", "1")
    monkeypatch.delenv("FAKE_CLAUDE_SCRIPT", raising=False)  # the real thing, not the shim
    monkeypatch.setenv("CANOPY_MAX_TURNS", "4")
    model = os.environ.get("CANOPY_LIVE_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("CANOPY_CLI_MODEL", model)
    monkeypatch.chdir(tmp_path)  # the adapter materializes assignments/<id>/ under cwd

    team = make_org(seed={"kind": "root", "roleKey": "backend-engineer"}, name="Live smoke")
    node = _node(team, "backend-engineer")
    # A keyless anthropic profile rides the operator's CLI login → the `subscription-cli`
    # ProviderAccount (02 §2.3) → the anthropic-max adapter (tier-2 S1/S2 + session-ok).
    s = mint_session(team["id"], node_id=node["id"], provider="anthropic", model=model)
    _seed_charter(team, s["actuationId"], node["id"])
    a = get_engine().submit_intent(
        team["id"], s["actuationId"],
        "LIVE SMOKE — do no work. Immediately call the canopy `finish` tool with the summary "
        "'live smoke ok' and an empty refs list, then stop. Do not read or write any files.",
        target_node=node["id"], allowance_override=20_000,
    ).assignment

    agent = _agent(s["token"])
    cfg = _cfg(live_server, s, node["id"])
    assert cli_runtime.cli_tick(agent, cfg) == "engaged"  # briefed → intake-complete
    assert cli_runtime.cli_tick(agent, cfg) == "engaged"  # planning → the real session
    _wait_session_done(a.id, timeout=240.0)

    # The done-bar: a tier-2 reading landed on the subscription account.
    acct = get_provider_accounts().find("anthropic", "subscription-cli")
    assert acct is not None, "the keyless anthropic profile should have derived the CLI account"
    with get_db().connect() as conn:
        tier2 = conn.execute(
            "SELECT COUNT(*) AS n FROM capacity_reading r JOIN capacity_window w"
            " ON w.id = r.window_id WHERE w.account_id = ? AND r.source = 'provider-event'",
            (acct.id,),
        ).fetchone()["n"]
    assert tier2 >= 1, "no provider-event reading — did the session end without a result?"
    five_hour = get_capacity_ledger().window(acct.id, "five_hour")
    assert five_hour is not None and five_hour["source"] == "provider-event"
    assert five_hour["state"] in ("ok", "warning", "exhausted")

    # And the console says so, with source + age (06 §1: no bare numbers).
    agg = client.get("/api/capacity").json()
    pool = next(p for p in agg["accounts"] if p["id"] == acct.id)
    shown = next(w for w in pool["windows"] if w["key"] == "five_hour")
    assert shown["source"] == "provider-event" and shown["ageS"] is not None

    # The money path metered the real session: at least one settled step on the assignment.
    detail = client.get(f"/api/assignments/{a.id}").json()
    assert len(detail["steps"]) >= 1
    assert detail["assignment"]["sessionRef"]  # the resume handle from system/init
