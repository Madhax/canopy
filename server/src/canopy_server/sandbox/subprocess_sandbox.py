"""``SubprocessSandbox`` — one OS subprocess per agent (sandbox.md §2).

Soft isolation, honestly labeled: v1 trusts the agent runtime code, not the OS. The security that
*is* real comes from the mediation chokepoints — the process gets a clean, whitelisted environment
(never inherited), holds no API key (only a revocable run token), and binds loopback. Windows is
the primary dev target (risk IM-3): tree termination uses ``taskkill /T`` on Windows and process
groups + ``killpg`` on POSIX; all paths go through ``pathlib``; no POSIX-only calls at import time.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

from .base import SandboxHandle, SandboxProvider, SandboxSpec, SandboxStatus

_RUNTIME_MODULE = "canopy_agent"


def _free_loopback_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
        )
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SubprocessSandbox(SandboxProvider):
    key = "subprocess"

    def __init__(self, argv: list[str] | None = None) -> None:
        # In production this is always the agent module; tests inject a trivial process to exercise
        # the lifecycle (spawn / status / tree-kill) without a real agent.
        self._argv = argv or [sys.executable, "-m", _RUNTIME_MODULE]
        self._procs: dict[str, subprocess.Popen] = {}
        self._specs: dict[str, SandboxSpec] = {}
        self._logfiles: dict[str, Path] = {}

    def _hid(self, spec_or_handle) -> str:
        return f"{spec_or_handle.actuation_id}::{spec_or_handle.node_id}"

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        workspace = spec.workspace_root
        workspace.mkdir(parents=True, exist_ok=True)
        logs_dir = workspace.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        hid = self._hid(spec)
        self._specs[hid] = spec
        self._logfiles[hid] = logs_dir / f"{spec.node_id}.log"
        # The agent binds an ephemeral loopback port and reports its endpoint at register
        # (sandbox.md §1: "None ⇒ provider/agent picks and reports at register").
        return SandboxHandle(
            id=hid,
            actuation_id=spec.actuation_id,
            node_id=spec.node_id,
            a2a_host=spec.a2a_host,
            a2a_port=spec.a2a_port,
            workspace_root=str(workspace),
        )

    async def start(self, handle: SandboxHandle) -> SandboxHandle:
        spec = self._specs.get(handle.id)
        if spec is None:
            raise RuntimeError(f"sandbox {handle.id} was not created before start()")

        log_fh = open(self._logfiles[handle.id], "ab")  # noqa: SIM115 - closed in stop/destroy
        kwargs: dict = {
            "cwd": str(spec.workspace_root),
            "env": spec.env,
            "stdout": log_fh,
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True  # own process group for killpg

        proc = subprocess.Popen(self._argv, **kwargs)
        self._procs[handle.id] = proc
        return handle.model_copy(update={"pid": proc.pid})

    async def stop(self, handle: SandboxHandle, grace_s: int = 10) -> None:
        proc = self._procs.get(handle.id)
        pid = handle.pid or (proc.pid if proc else None)
        if pid is None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True
            )
        else:
            import signal

            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            for _ in range(max(1, grace_s * 5)):
                if proc is not None and proc.poll() is not None:
                    break
                if not _pid_alive(pid):
                    break
                await asyncio.sleep(0.2)
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if proc is not None:
            try:
                proc.wait(timeout=grace_s)
            except Exception:  # noqa: BLE001
                pass
        self._procs.pop(handle.id, None)

    async def destroy(self, handle: SandboxHandle) -> None:
        await self.stop(handle)
        spec = self._specs.pop(handle.id, None)
        self._logfiles.pop(handle.id, None)
        if spec is not None and not spec.keep_workspace_on_destroy:
            import shutil

            node_root = spec.workspace_root.parent
            shutil.rmtree(node_root, ignore_errors=True)

    async def status(self, handle: SandboxHandle) -> SandboxStatus:
        proc = self._procs.get(handle.id)
        if proc is not None:
            rc = proc.poll()
            return (
                SandboxStatus(state="running")
                if rc is None
                else SandboxStatus(state="exited", exit_code=rc)
            )
        # No live Popen (e.g. the control plane restarted): fall back to pid liveness. The
        # authoritative liveness signal in that case is the directory heartbeat (control-plane §2).
        if handle.pid and _pid_alive(handle.pid):
            return SandboxStatus(state="running")
        return SandboxStatus(state="unknown")

    async def logs(self, handle: SandboxHandle, tail: int = 200) -> str:
        path = self._logfiles.get(handle.id)
        if path is None or not path.is_file():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-tail:])
