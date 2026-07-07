"""The agent runtime loop (agent-runtime.md §1).

Boot is charter-driven and stateless: read env → fetch charter → prepare workspace → start the
card server → register → heartbeat. Restart = the same sequence. The step loop, the tool surface,
and the full A2A task server are A3/A4; A2 proves the fabric — the process is up, serves its Agent
Card, is registered in the directory, and heartbeats. Only ``httpx`` + the stdlib are used; this
module never imports ``canopy_server``.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

HEARTBEAT_SECONDS = 10
CHARTER_RETRY_SECONDS = 30


def _log(event: str, **fields: object) -> None:
    """Structured stderr log — captured by the sandbox provider (agent-runtime.md §5)."""
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **fields}
    print(json.dumps(record), file=sys.stderr, flush=True)


@dataclass
class AgentConfig:
    cp_url: str
    run_token: str
    node_id: str
    actuation_id: str
    a2a_host: str
    a2a_port: int  # 0 ⇒ ephemeral


def load_config() -> AgentConfig:
    def req(name: str) -> str:
        v = os.environ.get(name)
        if not v:
            raise SystemExit(f"canopy-agent: missing required env {name}")
        return v

    raw_port = os.environ.get("CANOPY_A2A_PORT", "0")
    return AgentConfig(
        cp_url=req("CANOPY_CP_URL").rstrip("/"),
        run_token=req("CANOPY_RUN_TOKEN"),
        node_id=req("CANOPY_NODE_ID"),
        actuation_id=req("CANOPY_ACTUATION_ID"),
        a2a_host=os.environ.get("CANOPY_A2A_HOST", "127.0.0.1"),
        a2a_port=int(raw_port) if raw_port.isdigit() else 0,
    )


def fetch_charter(client: httpx.Client) -> dict:
    deadline = time.monotonic() + CHARTER_RETRY_SECONDS
    last: str = "no response"
    while time.monotonic() < deadline:
        try:
            r = client.get("/api/dp/charter")
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except httpx.HTTPError as exc:
            last = str(exc)
        time.sleep(0.5)
    raise SystemExit(f"canopy-agent: charter never became available ({last})")


def prepare_workspace(layout: dict) -> None:
    cwd = Path.cwd()
    for key in ("brief", "work", "out"):
        (cwd / layout.get(key, key)).mkdir(parents=True, exist_ok=True)
    memory = cwd / layout.get("memory", "memory.json")
    if not memory.exists():
        memory.write_text("{}", encoding="utf-8")


def build_card(charter: dict, endpoint: str) -> dict:
    """A minimal Agent-Card-shaped document (A3 swaps in a proper a2a-sdk card).

    Provider/model are deliberately absent — the card advertises capability, not configuration.
    """
    skills = [{"id": charter.get("roleKey", "role"), "name": charter.get("displayName", "agent")}]
    return {
        "protocolVersion": "0.1",
        "name": charter.get("displayName", charter.get("nodeId", "agent")),
        "description": charter.get("instructions", "")[:280],
        "url": endpoint,
        "version": "0.1.0",
        "capabilities": {"streaming": False},
        "skills": skills,
        "canopy": {
            "nodeId": charter.get("nodeId"),
            "roleKey": charter.get("roleKey"),
            "isManager": charter.get("isManager", False),
        },
    }


class _CardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        card = getattr(self.server, "card", {})
        path = self.path.rstrip("/")
        if path == "/card":
            self._json(200, card)
        elif path == "/health":
            self._json(200, {"status": "idle"})
        elif path == "/received":
            # A3 verification surface: what the router has delivered to this agent so far.
            self._json(200, {"received": getattr(self.server, "received", [])})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        # The router (never a peer) forwards mediated messages here. In A2/A3 the agent just
        # records the delivery; the step loop that acts on it arrives in A4.
        if self.path.rstrip("/") != "/inbox":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except ValueError:
            self._json(400, {"error": "bad envelope"})
            return
        received = getattr(self.server, "received", None)
        if received is not None:
            received.append(envelope)
        _log("delivered", **{
            "from": envelope.get("fromNodeId"),
            "kind": envelope.get("kind"),
            "messageId": envelope.get("id"),
        })
        self._json(200, {"ok": True})

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:  # silence default access logging
        pass


def start_card_server(host: str, port: int) -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer((host, port), _CardHandler)
    actual_port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, actual_port


def main() -> None:
    cfg = load_config()
    _log("boot", node=cfg.node_id, actuation=cfg.actuation_id)
    client = httpx.Client(
        base_url=cfg.cp_url,
        headers={"Authorization": f"Bearer {cfg.run_token}"},
        timeout=10.0,
    )

    charter = fetch_charter(client)
    prepare_workspace(charter.get("workspaceLayout", {}))

    server, port = start_card_server(cfg.a2a_host, cfg.a2a_port)
    endpoint = f"http://{cfg.a2a_host}:{port}"
    server.card = build_card(charter, endpoint)  # type: ignore[attr-defined]
    server.received = []  # type: ignore[attr-defined]  # mediated deliveries land here (A3)

    client.post("/api/dp/register", json={"endpoint": endpoint, "card": server.card})  # type: ignore[attr-defined]
    _log("registered", node=cfg.node_id, endpoint=endpoint,
         role=charter.get("roleKey"), manager=charter.get("managerNodeId"))

    try:
        while True:
            try:
                client.post("/api/dp/heartbeat", json={"status": "idle"})
            except httpx.HTTPError as exc:
                _log("heartbeat_error", error=str(exc))
            time.sleep(HEARTBEAT_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        client.close()
