"""Load and integrity-check ``catalog/catalog.json`` at import time.

The catalog is static data (docs/org-chart-editor.md §3.1). We fail loud at startup if it is
malformed or has dangling cross-references, so a bad catalog never reaches the editor.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .models import ORG_SECTIONS, Catalog

# repo_root/server/src/canopy_server/catalog.py  ->  repo_root/catalog/catalog.json
_CATALOG_PATH = Path(__file__).resolve().parents[3] / "catalog" / "catalog.json"

_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Grant keys are dotted kebab (agent-envelope.md §3.1): e.g. workspace.rw, code.repo.write.
_GRANT_KEY_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")


class CatalogIntegrityError(Exception):
    pass


def check_integrity(catalog: Catalog) -> list[str]:
    """Return a list of integrity problems (empty == healthy)."""
    problems: list[str] = []

    role_keys = [r.key for r in catalog.roles]
    form_keys = [f.key for f in catalog.formations]
    org_keys = [o.key for o in catalog.organizationTypes]

    key_groups = (("role", role_keys), ("formation", form_keys), ("organizationType", org_keys))
    for label, keys in key_groups:
        seen: set[str] = set()
        for k in keys:
            if not _KEY_RE.match(k):
                problems.append(f"{label} key not kebab-case: {k!r}")
            if k in seen:
                problems.append(f"duplicate {label} key: {k!r}")
            seen.add(k)

    role_set = set(role_keys)
    form_set = set(form_keys)

    for o in catalog.organizationTypes:
        if o.section not in ORG_SECTIONS:
            problems.append(f"organizationType {o.key!r} has unknown section {o.section!r}")
        for rk in o.rolePalette:
            if rk not in role_set:
                problems.append(f"organizationType {o.key!r} palette -> unknown role {rk!r}")
        for fk in o.formations:
            if fk not in form_set:
                problems.append(f"organizationType {o.key!r} -> unknown formation {fk!r}")

    for f in catalog.formations:
        slots = {f.manager.slot} | {m.slot for m in f.members}
        if f.manager.roleKey not in role_set:
            problems.append(f"formation {f.key!r} manager -> unknown role {f.manager.roleKey!r}")
        for m in f.members:
            if m.roleKey not in role_set:
                problems.append(
                    f"formation {f.key!r} member {m.slot!r} -> unknown role {m.roleKey!r}"
                )
        for d in f.dependencies:
            if d.from_ not in slots:
                problems.append(f"formation {f.key!r} dependency from unknown slot {d.from_!r}")
            if d.to not in slots:
                problems.append(f"formation {f.key!r} dependency to unknown slot {d.to!r}")

    grant_keys: set[str] = set()
    for g in catalog.toolGrants:
        if not _GRANT_KEY_RE.match(g.key):
            problems.append(f"toolGrant key not dotted-kebab: {g.key!r}")
        if g.key in grant_keys:
            problems.append(f"duplicate toolGrant key: {g.key!r}")
        grant_keys.add(g.key)

    for r in catalog.roles:
        s = r.defaultSalary
        if not (isinstance(s.perAssignmentAllowance, int) and s.perAssignmentAllowance > 0):
            problems.append(f"role {r.key!r} defaultSalary allowance must be a positive int")
        if not (0 < s.warnThresholdPct <= 100):
            problems.append(f"role {r.key!r} defaultSalary warn threshold out of range")
        for gk in r.toolGrants:
            if gk not in grant_keys:
                problems.append(f"role {r.key!r} -> unknown toolGrant {gk!r}")

    return problems


def load_catalog(path: Path = _CATALOG_PATH) -> Catalog:
    raw = json.loads(path.read_text(encoding="utf-8"))
    catalog = Catalog.model_validate(raw)
    problems = check_integrity(catalog)
    if problems:
        raise CatalogIntegrityError(
            f"catalog.json failed integrity checks ({len(problems)}):\n  - "
            + "\n  - ".join(problems)
        )
    return catalog


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Cached catalog singleton (loaded + integrity-checked once)."""
    return load_catalog()
