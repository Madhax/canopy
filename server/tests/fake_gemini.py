"""The fake Gemini CLI shim: speaks the headless ``@google/gemini-cli`` ``stream-json`` contract
so the ``cli-gemini`` adapter + MCP server + ``google-consumer`` capacity adapter run end-to-end
with zero external calls (risk IM-2, CAP-D5).

Reads ``.gemini/settings.json`` in cwd for the ``canopy`` MCP server, emits Gemini ``stream-json``
events (``init`` → ``tool_use`` / ``tool_result`` / ``message`` → ``result`` with ``stats``), and
calls the Canopy MCP server over HTTP for scripted tools.
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
        data=json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--version":
        print("fake-gemini 0.1.0")
        return 0
    script_path = os.environ.get("FAKE_GEMINI_SCRIPT") or os.environ.get("FAKE_CLAUDE_SCRIPT")
    if not script_path:
        print("fake_gemini: FAKE_GEMINI_SCRIPT not set", file=sys.stderr)
        return 2
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))

    settings_path = Path(".gemini") / "settings.json"
    url, headers = None, {}
    if settings_path.is_file():
        conf = json.loads(settings_path.read_text(encoding="utf-8"))
        server = (conf.get("mcpServers") or {}).get("canopy") or {}
        url = server.get("httpUrl") or server.get("url")
        headers = server.get("headers") or {}

    resuming = _arg("--resume", argv) is not None
    turns = (
        script.get("resumeTurns")
        if resuming and "resumeTurns" in script
        else script.get("turns", [])
    )
    model = _arg("--model", argv) or "gemini-2.5-pro"

    _emit({
        "type": "init",
        "session_id": script.get("sessionId", "sess-gemini-fake"),
        "model": model,
    })

    total_in = 0
    total_out = 0
    total_cached = 0
    tool_calls = 0
    for turn in turns:
        for idx, tool in enumerate(turn.get("tools", [])):
            tool_calls += 1
            tid = f"call_{tool_calls}_{idx}"
            _emit({
                "type": "tool_use",
                "tool_name": f"mcp__canopy__{tool['name']}",
                "tool_id": tid,
                "parameters": tool.get("arguments", {}),
            })
            if url:
                try:
                    res = _mcp_call(url, headers, tool["name"], tool.get("arguments", {}))
                    if "error" in res:
                        print(
                            f"fake_gemini: MCP error on {tool['name']}: {res['error']}",
                            file=sys.stderr,
                        )
                except Exception as exc:  # noqa: BLE001
                    print(f"fake_gemini: MCP call failed: {exc}", file=sys.stderr)
            _emit({
                "type": "tool_result",
                "tool_id": tid,
                "status": "success",
                "output": "ok",
            })
        usage = turn.get("usage", [100, 20])
        total_in += int(usage[0])
        total_out += int(usage[1])
        if len(usage) > 2:
            total_cached += int(usage[2])
        _emit({
            "type": "message",
            "role": "assistant",
            "content": turn.get("text", "completed turn"),
        })

    stats = {
        "total_tokens": total_in + total_out,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "cached": total_cached,
        "duration_ms": 25,
        "tool_calls": tool_calls,
    }
    if script.get("limitResult"):
        _emit({
            "type": "result",
            "status": "error",
            "error": {"type": "QuotaError", "message": script["limitResult"]},
            "stats": stats,
        })
        return 1
    _emit({
        "type": "result",
        "status": "success",
        "stats": stats,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

