"""Schema migration for organization documents.

``schemaVersion`` gates loading. v1 is identity; anything above the known version is a hard error.
Runs before parse on the server (the Zod side mirrors this in ``ui/src/schema/migrate.ts``).
"""

from __future__ import annotations

from typing import Any

from .models import SCHEMA_VERSION


class UnsupportedSchemaVersion(Exception):
    def __init__(self, version: Any):
        self.version = version
        super().__init__(
            f"Unsupported organization schemaVersion: {version!r} "
            f"(this build understands up to {SCHEMA_VERSION})"
        )


def migrate_organization(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a document at the current ``schemaVersion``.

    v1 is identity. Recurses into nested child organizations so a mixed-version tree still
    migrates as one unit. Raises :class:`UnsupportedSchemaVersion` for versions we don't know.
    """
    if not isinstance(doc, dict):
        return doc
    version = doc.get("schemaVersion", SCHEMA_VERSION)
    if not isinstance(version, int) or version > SCHEMA_VERSION or version < 1:
        raise UnsupportedSchemaVersion(version)

    # v1: identity. Future versions add transforms here, low → high.
    for child in doc.get("childOrganizations", []) or []:
        if isinstance(child, dict) and isinstance(child.get("organization"), dict):
            child["organization"] = migrate_organization(child["organization"])
    return doc
