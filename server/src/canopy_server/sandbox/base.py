"""Sandbox provider ABC + the serializable spec/handle/status models (sandbox.md §1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Limits(BaseModel):
    """Best-effort in v1 (sandbox.md §2); real enforcement arrives with container providers."""

    max_rss_mb: int | None = None
    cpu_nice: int | None = None
    wall_clock_s: int | None = None


class SandboxSpec(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    actuation_id: str
    node_id: str
    org_id: str
    runtime: str = "canopy-agent"  # entrypoint identity; later: image ref for containers
    workspace_root: Path
    env: dict[str, str]  # STRICT WHITELIST built by the Actuator — never inherited
    a2a_host: str = "127.0.0.1"
    a2a_port: int | None = None  # None ⇒ provider picks a free loopback port
    limits: Limits = Limits()
    keep_workspace_on_destroy: bool = True


class SandboxHandle(BaseModel):
    id: str
    actuation_id: str
    node_id: str
    pid: int | None = None
    a2a_host: str = "127.0.0.1"
    a2a_port: int | None = None
    workspace_root: str
    started_at: str | None = None


class SandboxStatus(BaseModel):
    state: Literal["running", "exited", "unknown"]
    exit_code: int | None = None


class SandboxProvider(ABC):
    key: str

    @abstractmethod
    async def create(self, spec: SandboxSpec) -> SandboxHandle: ...

    @abstractmethod
    async def start(self, handle: SandboxHandle) -> SandboxHandle: ...

    @abstractmethod
    async def stop(self, handle: SandboxHandle, grace_s: int = 10) -> None: ...

    @abstractmethod
    async def destroy(self, handle: SandboxHandle) -> None: ...

    @abstractmethod
    async def status(self, handle: SandboxHandle) -> SandboxStatus: ...

    @abstractmethod
    async def logs(self, handle: SandboxHandle, tail: int = 200) -> str: ...
