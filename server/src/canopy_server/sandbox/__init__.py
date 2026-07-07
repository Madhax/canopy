"""Sandbox providers — the isolation boundary around one agent (sandbox.md).

``SandboxProvider`` is selected by ``[sandbox] provider`` in canopy.toml. v1 ships ``subprocess``;
``docker``/``microvm``/``remote`` slot in behind the same ABC later (roadmap.md) — the only planned
interface change is ``SandboxSpec.runtime`` becoming an OCI image reference, reserved now.
"""

from __future__ import annotations

from ..registry import Registry
from .base import Limits, SandboxHandle, SandboxProvider, SandboxSpec, SandboxStatus
from .subprocess_sandbox import SubprocessSandbox

sandbox_registry: Registry[SandboxProvider] = Registry("sandbox provider")
sandbox_registry.register("subprocess")(SubprocessSandbox)

__all__ = [
    "Limits",
    "SandboxHandle",
    "SandboxProvider",
    "SandboxSpec",
    "SandboxStatus",
    "SubprocessSandbox",
    "sandbox_registry",
]
