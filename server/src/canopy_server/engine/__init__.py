"""Execution Engine — the control-plane module that owns work truth (engine.md).

Runtimes own nothing: every interaction is a *report* ("intake done", "step happened",
"delivering refs") or a *request* ("delegate", "escalate", "finish") against the caller's own
assignment. The engine validates against the charter-derived topology, mutates work state, meters
via the A1 ledger, routes via the A3 bus, and stores outputs in the E1 Artifact Store.

Package layout:
* ``models`` — the Pydantic boundary shapes and state enums for every work-layer object.
* ``store``  — :class:`WorkStore`, the persistence layer over the ``work_*`` tables.
* ``engine`` — :class:`ExecutionEngine`, the orchestration built on the store + ledger + router
  + artifact store (added in the next E1 slice).
"""

from __future__ import annotations

from .models import (
    Assignment,
    Brief,
    Deliverable,
    Intent,
    MemoryEntry,
    Plan,
    PlanStage,
    Step,
)
from .store import WorkStore

__all__ = [
    "Assignment",
    "Brief",
    "Deliverable",
    "Intent",
    "MemoryEntry",
    "Plan",
    "PlanStage",
    "Step",
    "WorkStore",
]
