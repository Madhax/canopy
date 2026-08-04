"""The SSE events channel (engine.md §6) — `GET /organizations/{id}/events`.

One live stream per org: activity transitions ride through individually with seq ids (so
Last-Event-ID resume works); step/plan/note/notification changes arrive as coalesced per-family
events. The tail is DB-driven — anything that lands in the store surfaces without engine hooks.

The stream logic is tested by driving the generator directly (a TestClient never delivers a
disconnect, so an in-client stream would hang teardown); the HTTP wiring gets one real-uvicorn
smoke test, same pattern as the cli-runtime integration suite.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import pytest

from canopy_server.routes import work as work_routes


@pytest.fixture(autouse=True)
def fast_ticks(monkeypatch):
    monkeypatch.setattr(work_routes, "EVENTS_TICK_SECONDS", 0.02)


class _StubRequest:
    """Never disconnects — the tests stop pulling and close the generator instead."""

    async def is_disconnected(self) -> bool:
        return False


def _root_of(org: dict) -> dict:
    return next(a for a in org["agents"] if a["managerId"] is None)


def _seed_live_actuation(actuation_id: str, org_id: str) -> None:
    from canopy_server.deps import get_db, now_iso

    ts = now_iso()
    with get_db().transaction() as conn:
        conn.execute(
            "INSERT INTO actuation (id, org_id, state, created_at, updated_at) VALUES (?,?,?,?,?)",
            (actuation_id, org_id, "live", ts, ts),
        )


def _submit_intent(client, make_org, mint_session, text="Add CSV export") -> dict:
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    root = _root_of(org)
    s = mint_session(org["id"], node_id=root["id"])
    _seed_live_actuation(s["actuationId"], org["id"])
    r = client.post(
        f"/api/organizations/{org['id']}/intents",
        json={"text": text, "targetNodeId": root["id"]},
    )
    assert r.status_code == 201, r.text
    return {"org": org, "intent": r.json()["intent"], "assignment": r.json()["assignment"]}


def _parse_events(chunks: list[str]) -> list[dict]:
    """Fold raw SSE text into [{event, data, id?}] message dicts (comments dropped)."""
    events, current = [], {}
    for line in "".join(chunks).split("\n"):
        if line == "":
            if current:
                events.append(current)
            current = {}
        elif line.startswith("event: "):
            current["event"] = line[len("event: "):]
        elif line.startswith("data: "):
            current["data"] = json.loads(line[len("data: "):])
        elif line.startswith("id: "):
            current["id"] = int(line[len("id: "):])
    return events


def _drive_stream(org_id: str, after: int | None, until, between_ticks=None) -> list[str]:
    """Pull SSE chunks from the generator until ``until(chunks)`` is true. ``between_ticks``
    (if given) runs once after the first chunk — the writes-after-baseline hook."""
    from canopy_server.deps import get_activity, get_work_store

    async def run() -> list[str]:
        gen = work_routes._org_event_stream(
            _StubRequest(), org_id, after, get_activity(), get_work_store()
        )
        chunks: list[str] = []
        try:
            deadline = time.monotonic() + 15
            while not until(chunks):
                assert time.monotonic() < deadline, f"expected output never came: {chunks}"
                chunks.append(await asyncio.wait_for(gen.__anext__(), timeout=5))
                if between_ticks is not None and len(chunks) == 1:
                    between_ticks()
        finally:
            await gen.aclose()
        return chunks

    return asyncio.run(run())


def test_stream_replays_activity_from_cursor(client, make_org, mint_session):
    """`after=0` replays the org's whole activity tail — each row one event, id = seq."""
    ctx = _submit_intent(client, make_org, mint_session)

    chunks = _drive_stream(
        ctx["org"]["id"], 0,
        lambda cs: any(
            e.get("event") == "activity" and e["data"]["kind"] == "intent.submitted"
            for e in _parse_events(cs)
        ),
    )
    events = _parse_events(chunks)
    assert events[0] == {"event": "hello", "data": {"seq": 0}}
    submitted = next(e for e in events if e.get("event") == "activity")
    assert submitted["id"] == submitted["data"]["seq"]
    assert ctx["intent"]["id"] in submitted["data"]["subjectIds"]


def test_stream_coalesces_store_changes(client, make_org, mint_session):
    """Without a cursor the stream starts at 'now'; store writes after the baseline surface as
    one coalesced event per family — no engine hooks involved."""
    from canopy_server.deps import get_work_store

    ctx = _submit_intent(client, make_org, mint_session)
    org_id = ctx["org"]["id"]

    def write_after_baseline() -> None:
        ws = get_work_store()
        ws.notify(org_id, "info", "intent-completed", "done", subject_ids=[ctx["intent"]["id"]])
        ws.create_note(org_id, ctx["intent"]["id"], "steer left",
                       assignment_id=ctx["assignment"]["id"])

    chunks = _drive_stream(
        org_id, None,
        lambda cs: {"notifications", "notes"}
        <= {e.get("event") for e in _parse_events(cs)},
        between_ticks=write_after_baseline,
    )
    events = _parse_events(chunks)
    assert events[0]["event"] == "hello"
    assert events[0]["data"]["seq"] > 0  # baseline cursor is 'now', not a replay
    # The intent.submitted activity predates the baseline — it must NOT be replayed.
    assert not any(e.get("event") == "activity" for e in events)


def test_stream_keepalive_when_quiet(client, make_org):
    """A quiet org still gets comment keepalives, so proxies/clients keep the socket open."""
    org = make_org(seed={"kind": "root", "roleKey": "engineering-lead"})
    chunks = _drive_stream(org["id"], None, lambda cs: any(c.startswith(":") for c in cs))
    assert ": keepalive\n\n" in chunks


def test_events_step_watermark(client, make_org, mint_session):
    """A recorded step moves the steps family (joined through the assignment for org scoping)."""
    from canopy_server.deps import get_engine, get_work_store

    ctx = _submit_intent(client, make_org, mint_session)
    org_id = ctx["org"]["id"]
    before = get_work_store().change_watermark(org_id)
    get_engine().record_step(
        ctx["assignment"]["id"], input_tokens=10, output_tokens=5, duration_ms=100,
    )
    after = get_work_store().change_watermark(org_id)
    assert after["steps"] == (before["steps"][0] + 1,)
    assert after["plan"] == before["plan"] and after["notes"] == before["notes"]


def test_events_unknown_org_404(client):
    assert client.get("/api/organizations/nope/events").status_code == 404


def test_events_over_http(client, make_org, mint_session):
    """The wire itself: a real uvicorn thread, a real socket — headers, replay, clean close."""
    import httpx
    import uvicorn

    from canopy_server.main import app

    ctx = _submit_intent(client, make_org, mint_session)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn thread never started")
        time.sleep(0.05)
    try:
        url = f"http://127.0.0.1:{port}/api/organizations/{ctx['org']['id']}/events?after=0"
        lines: list[str] = []
        with httpx.stream("GET", url, timeout=10) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            for line in r.iter_lines():
                lines.append(line)
                if any(
                    e.get("event") == "activity"
                    and e.get("data", {}).get("kind") == "intent.submitted"
                    for e in _parse_events(["\n".join(lines) + "\n"])
                ):
                    break
                assert len(lines) < 400, f"expected activity never arrived: {lines}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
