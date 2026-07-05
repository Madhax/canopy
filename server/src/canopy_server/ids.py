"""Id generation. Agent/dependency ids are ``a_``/``d_`` + nanoid(8) (docs §3.3).

The UI generates these client-side so editing never blocks on the server; the server generates
them only when it materializes agents itself (seeds, formation stamps, import re-id).
"""

from __future__ import annotations

import uuid

from nanoid import generate

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def new_agent_id() -> str:
    return "a_" + generate(_ALPHABET, 8)


def new_dependency_id() -> str:
    return "d_" + generate(_ALPHABET, 8)


def new_document_id() -> str:
    return str(uuid.uuid4())
