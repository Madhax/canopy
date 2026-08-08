"""SubprocessSandbox lifecycle — spawn, status, tree-kill (Windows + POSIX, risk IM-3).

Uses a trivial injected process (a Python sleep) rather than the real agent, so this exercises the
process-orchestration mechanics in isolation. This is the core content of the CI matrix.
"""

from __future__ import annotations

import asyncio
import os
import sys

from canopy_server.sandbox import SandboxSpec, SubprocessSandbox


def _env() -> dict[str, str]:
    # Enough for the interpreter to start on both platforms (Windows needs SystemRoot).
    keys = ("PATH", "SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "PYTHONHOME")
    return {k: os.environ[k] for k in keys if k in os.environ}


def test_spawn_status_stop(tmp_path):
    sandbox = SubprocessSandbox(
        argv=[sys.executable, "-c", "import time; time.sleep(60)"]
    )
    spec = SandboxSpec(
        actuation_id="act1",
        node_id="n1",
        org_id="o1",
        workspace_root=tmp_path / "ws",
        env=_env(),
        a2a_port=None,
    )

    async def run():
        handle = await sandbox.create(spec)
        assert (tmp_path / "ws").is_dir()  # provider created the workspace
        handle = await sandbox.start(handle)
        assert handle.pid is not None
        assert (await sandbox.status(handle)).state == "running"

        await sandbox.stop(handle, grace_s=5)
        assert (await sandbox.status(handle)).state in ("exited", "unknown")

    asyncio.run(run())


def test_stable_log_dir_wins_and_survives_destroy(tmp_path):
    """F16: with ``log_dir`` set, the adapter log lands in the stable home (not the
    per-actuation shard) and outlives destroy — the org keeps its process record."""
    sandbox = SubprocessSandbox(
        argv=[sys.executable, "-c", "print('proof of boot')"]
    )
    stable_logs = tmp_path / "work" / "o1" / "n3" / "logs"
    spec = SandboxSpec(
        actuation_id="act1",
        node_id="n3",
        org_id="o1",
        workspace_root=tmp_path / "sandboxes" / "act1" / "n3" / "workspace",
        log_dir=stable_logs,
        env=_env(),
        keep_workspace_on_destroy=False,
    )

    async def run():
        handle = await sandbox.create(spec)
        handle = await sandbox.start(handle)
        for _ in range(50):
            if (await sandbox.status(handle)).state == "exited":
                break
            await asyncio.sleep(0.1)
        await sandbox.destroy(handle)

    asyncio.run(run())
    log = stable_logs / "n3.log"
    assert log.is_file() and "proof of boot" in log.read_text()
    assert not (tmp_path / "sandboxes" / "act1" / "n3").exists()  # scratch pruned
    assert not (tmp_path / "sandboxes" / "act1" / "n3" / "logs").exists()


def test_destroy_removes_workspace_when_requested(tmp_path):
    sandbox = SubprocessSandbox(argv=[sys.executable, "-c", "pass"])
    spec = SandboxSpec(
        actuation_id="act1",
        node_id="n2",
        org_id="o1",
        workspace_root=tmp_path / "node" / "workspace",
        env=_env(),
        keep_workspace_on_destroy=False,
    )

    async def run():
        handle = await sandbox.create(spec)
        handle = await sandbox.start(handle)
        await sandbox.destroy(handle)

    asyncio.run(run())
    assert not (tmp_path / "node").exists()  # node dir pruned
