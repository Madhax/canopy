"""Schema migration for team documents.

``schemaVersion`` gates loading. v1 (``canopy.organization``) migrates to v2 (``canopy.team``):
kind rewrite, ``childOrganizations[].organization`` → ``childTeams[].team``. v1 documents are
accepted **indefinitely** — import is the compatibility surface; export always emits v2
(``design/organizations/07-implementation-plan.md`` §2.2). Anything above the known version is a
hard error. Runs before parse on the server (the Zod side mirrors this in
``ui/src/schema/migrate.ts``).
"""

from __future__ import annotations

from typing import Any

from .models import SCHEMA_VERSION


class UnsupportedSchemaVersion(Exception):
    def __init__(self, version: Any):
        self.version = version
        super().__init__(
            f"Unsupported team schemaVersion: {version!r} "
            f"(this build understands up to {SCHEMA_VERSION})"
        )


def migrate_team(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a document at the current ``schemaVersion``.

    v1 → v2: ``kind`` becomes ``canopy.team``, ``childOrganizations`` becomes ``childTeams``
    with each entry's ``organization`` key becoming ``team``. Recurses into nested children so a
    mixed-version tree still migrates as one unit. Raises :class:`UnsupportedSchemaVersion` for
    versions we don't know.
    """
    if not isinstance(doc, dict):
        return doc
    version = doc.get("schemaVersion", SCHEMA_VERSION)
    if not isinstance(version, int) or version > SCHEMA_VERSION or version < 1:
        raise UnsupportedSchemaVersion(version)

    if version < 2 or doc.get("kind") == "canopy.organization":
        doc["kind"] = "canopy.team"
        doc["schemaVersion"] = SCHEMA_VERSION
        if "childOrganizations" in doc:
            children = doc.pop("childOrganizations") or []
            migrated_children = []
            for child in children:
                if isinstance(child, dict) and "organization" in child:
                    child = dict(child)
                    child["team"] = child.pop("organization")
                migrated_children.append(child)
            doc["childTeams"] = migrated_children

    # Recurse (covers already-v2 children and freshly renamed ones alike).
    for child in doc.get("childTeams", []) or []:
        if isinstance(child, dict) and isinstance(child.get("team"), dict):
            child["team"] = migrate_team(child["team"])
    return doc


# Back-compat alias for any straggling caller; the C1 sweep removes uses.
migrate_organization = migrate_team
