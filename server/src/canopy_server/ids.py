"""Id generation. Agent/dependency ids are ``a_``/``d_`` + nanoid(8) (docs §3.3).

The UI generates these client-side so editing never blocks on the server; the server generates
them only when it materializes agents itself (seeds, formation stamps, import re-id).
"""

from __future__ import annotations

import secrets
import uuid

from nanoid import generate

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def new_agent_id() -> str:
    return "a_" + generate(_ALPHABET, 8)


def new_dependency_id() -> str:
    return "d_" + generate(_ALPHABET, 8)


def new_document_id() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Phase-2 (actuation) ids. Prefixes echo the docs (`ap_`, `sec_`) and keep every
# id self-describing in logs and the activity feed.
# --------------------------------------------------------------------------- #
def _prefixed(prefix: str, n: int = 10) -> str:
    return f"{prefix}_" + generate(_ALPHABET, n)


def new_profile_id() -> str:
    return _prefixed("ap")


def new_binding_id() -> str:
    return _prefixed("ab")


def new_secret_id() -> str:
    return _prefixed("sec")


def new_actuation_id() -> str:
    return _prefixed("act")


def new_meter_id() -> str:
    return _prefixed("mt")


def new_step_id() -> str:
    return _prefixed("st")


def new_spend_id() -> str:
    return _prefixed("se")


def new_run_token_record_id() -> str:
    return _prefixed("rt")


def new_activity_id() -> str:
    return _prefixed("ev")


def new_task_id() -> str:
    return _prefixed("tk")


def new_message_id() -> str:
    return _prefixed("msg")


def new_channel_id() -> str:
    return _prefixed("ch")


# --------------------------------------------------------------------------- #
# Phase-3 (execution / work layer) ids — prefixes per docs/execution/work-model.md.
# --------------------------------------------------------------------------- #
def new_intent_id() -> str:
    return _prefixed("in")


def new_assignment_id() -> str:
    return _prefixed("as")


def new_gate_id() -> str:
    return _prefixed("gt")


def new_plan_id() -> str:
    return _prefixed("pl")


def new_deliverable_id() -> str:
    return _prefixed("dv")


def new_directive_id() -> str:
    return _prefixed("dr")


def new_cadence_id() -> str:
    return _prefixed("cd")


def new_notification_id() -> str:
    return _prefixed("nt")


def new_artifact_id() -> str:
    return _prefixed("art")


def new_run_token() -> str:
    """A 256-bit URL-safe run-token secret (stored only as a hash — sandbox.md §2)."""
    return secrets.token_urlsafe(32)
