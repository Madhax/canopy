"""The fake-CLI shim (cli-runtime.md §9): speaks the headless Claude Code contract so the
cli-claude adapter + MCP server integration runs with zero external calls (risk IM-2).

Reads ``-p``/``--resume``/``--mcp-config`` like the real CLI, emits canned stream-json
(init → assistant turns with usage → result), and ACTUALLY calls the Canopy MCP server for the
scripted tool sequence — the same wire the real CLI would use.

The script comes from ``FAKE_CLAUDE_SCRIPT`` (a JSON file)::

    {"sessionId": "sess-1",
     "turns": [{"tools": [{"name": "declare_plan", "arguments": {...}}],
                "usage": [120, 40]}]}

On ``--resume``, ``resumeTurns`` is used instead of ``turns`` when present.

The C2 limit vocabulary (design/organizations/03 §4 — tier-2 parsing must be CI-truth):

* a turn may carry ``"apiRetry": {"error": "rate_limit", "error_status": 429,
  "retry_delay_ms": 1200}`` — emitted as a ``system/api_retry`` event before the turn;
* the script may set ``"limitResult": "Claude AI usage limit reached|<epoch>"`` (or the
  interactive phrasing) — the final ``result`` becomes an error carrying that text,
  exactly the S1 shape the real CLI emits at exhaustion.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path


def _arg(flag: str, argv: list[str]) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv else None


def _emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _mcp_call(url: str, headers: dict, name: str, arguments: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                         "params": {"name": name, "arguments": arguments}}).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def main() -> int:
    argv = sys.argv[1:]
    script_path = os.environ.get("FAKE_CLAUDE_SCRIPT")
    if argv and argv[0] == "--version":
        print("fake-claude 0.0.1")
        return 0
    if not script_path:
        print("fake_claude: FAKE_CLAUDE_SCRIPT not set", file=sys.stderr)
        return 2
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))

    mcp_conf_path = _arg("--mcp-config", argv)
    url, headers = None, {}
    if mcp_conf_path:
        conf = json.loads(Path(mcp_conf_path).read_text(encoding="utf-8"))
        server = conf["mcpServers"]["canopy"]
        url, headers = server["url"], server.get("headers", {})

    resuming = _arg("--resume", argv) is not None
    turns = script.get("resumeTurns") if resuming and "resumeTurns" in script \
        else script.get("turns", [])

    _emit({"type": "system", "subtype": "init",
           "session_id": script.get("sessionId", "sess-fake"),
           "model": "claude-fake", "tools": []})

    for turn in turns:
        if "apiRetry" in turn:
            _emit({"type": "system", "subtype": "api_retry", **turn["apiRetry"]})
        content = []
        for tool in turn.get("tools", []):
            content.append({"type": "tool_use", "name": f"mcp__canopy__{tool['name']}",
                            "input": tool.get("arguments", {})})
            if url:
                try:
                    res = _mcp_call(url, headers, tool["name"], tool.get("arguments", {}))
                    if "error" in res:
                        print(f"fake_claude: MCP error on {tool['name']}: "
                              f"{res['error']}", file=sys.stderr)
                except Exception as exc:  # noqa: BLE001 - shim mirrors CLI resilience
                    print(f"fake_claude: MCP call failed: {exc}", file=sys.stderr)
        usage = turn.get("usage", [100, 20])
        _emit({"type": "assistant",
               "message": {"content": content,
                           "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}}})

    if script.get("limitResult"):
        _emit({"type": "result", "subtype": "error_during_execution", "is_error": True,
               "result": script["limitResult"], "total_cost_usd": 0.0,
               "num_turns": len(turns), "usage": {}})
        return 1
    _emit({"type": "result", "subtype": "success", "total_cost_usd": 0.0,
           "num_turns": len(turns), "usage": {}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
