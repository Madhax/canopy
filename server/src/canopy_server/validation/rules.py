"""The authoritative validation rule set (docs/org-chart-editor.md §4.1).

``validate_organization`` walks a top-level :class:`~canopy_server.models.Organization` and every
nested child organization, returning a flat list of :class:`ValidationIssue`. Nested issues carry an
``orgPath`` (the list of child-org ids from the top document down to the offending level).

Two modes:

- ``draft``   — ``NO_ROOT`` / ``MULTIPLE_ROOTS`` are warnings (never lose work to validation).
- ``export``  — full severity; the export endpoint refuses while any error exists anywhere.
"""

from __future__ import annotations

from ..models import Catalog, Organization
from .codes import Mode, ValidationIssue, issue


def _role_index(catalog: Catalog | None) -> dict[str, set[int]]:
    idx: dict[str, set[int]] = {}
    if catalog:
        for r in catalog.roles:
            idx.setdefault(r.key, set()).add(r.version)
    return idx


def _valid_salary(salary) -> bool:
    return (
        isinstance(salary.perAssignmentAllowance, int)
        and salary.perAssignmentAllowance > 0
        and 0 < salary.warnThresholdPct <= 100
    )


def validate_organization(
    org: Organization,
    mode: Mode = "draft",
    catalog: Catalog | None = None,
    *,
    _path: list[str] | None = None,
    _catalog_index: dict[str, set[int]] | None = None,
) -> list[ValidationIssue]:
    path = _path or []
    role_idx = _catalog_index if _catalog_index is not None else _role_index(catalog)
    issues: list[ValidationIssue] = []
    root_severity = "warning" if mode == "draft" else "error"

    agents = org.agents
    deps = org.dependencies
    children = org.childOrganizations

    agent_ids = {a.id for a in agents}
    child_org_ids = {c.organization.id for c in children}
    # Dependency endpoints may be agents OR mounted child orgs (opaque, as a sibling).
    endpoint_ids = agent_ids | child_org_ids

    # Parent map: an agent's parent is its managerId; a child org's parent is its mountAgentId.
    parent_of: dict[str, str | None] = {a.id: a.managerId for a in agents}
    for c in children:
        parent_of[c.organization.id] = c.mountAgentId

    # -- DUPLICATE_ID (agents, then dependencies) ---------------------------
    agent_dupes = _duplicates([a.id for a in agents])
    if agent_dupes:
        issues.append(issue("DUPLICATE_ID", "error", agentIds=agent_dupes, orgPath=path))
    dep_dupes = _duplicates([d.id for d in deps])
    if dep_dupes:
        issues.append(issue("DUPLICATE_ID", "error", dependencyIds=dep_dupes, orgPath=path))

    # -- Roots --------------------------------------------------------------
    roots = [a.id for a in agents if a.managerId is None]
    if len(roots) == 0 and agents:
        issues.append(issue("NO_ROOT", root_severity, orgPath=path))
    elif len(roots) == 0 and not agents:
        # Truly empty org: still flag NO_ROOT so export gates on it.
        issues.append(issue("NO_ROOT", root_severity, orgPath=path))
    if len(roots) > 1:
        issues.append(issue("MULTIPLE_ROOTS", root_severity, agentIds=roots, orgPath=path))

    # -- MANAGER_DANGLING ---------------------------------------------------
    for a in agents:
        if a.managerId is not None and a.managerId not in agent_ids:
            issues.append(issue("MANAGER_DANGLING", "error", agentIds=[a.id], orgPath=path))

    # -- REPORTS_CYCLE ------------------------------------------------------
    cycle_nodes = _reporting_cycle_nodes(agents, agent_ids)
    if cycle_nodes:
        issues.append(issue("REPORTS_CYCLE", "error", agentIds=sorted(cycle_nodes), orgPath=path))

    # -- MOUNT_DANGLING -----------------------------------------------------
    for c in children:
        if c.mountAgentId not in agent_ids:
            issues.append(
                issue("MOUNT_DANGLING", "error", agentIds=[c.mountAgentId], orgPath=path)
            )

    # -- Dependencies -------------------------------------------------------
    seen_pairs: set[tuple[str, str]] = set()
    for d in deps:
        if d.from_ == d.to:
            issues.append(issue("DEP_SELF", "error", dependencyIds=[d.id], orgPath=path))
            continue
        if d.from_ not in endpoint_ids or d.to not in endpoint_ids:
            issues.append(issue("DEP_DANGLING", "error", dependencyIds=[d.id], orgPath=path))
            continue
        pair = (d.from_, d.to)
        if pair in seen_pairs:
            issues.append(issue("DEP_DUPLICATE", "error", dependencyIds=[d.id], orgPath=path))
        seen_pairs.add(pair)
        if parent_of.get(d.from_) != parent_of.get(d.to):
            issues.append(
                issue("DEP_NOT_SIBLINGS", "error", dependencyIds=[d.id], orgPath=path)
            )

    cyclic_deps = _dependency_cycle_ids(deps, endpoint_ids)
    if cyclic_deps:
        issues.append(issue("DEP_CYCLE", "error", dependencyIds=sorted(cyclic_deps), orgPath=path))

    # -- Roles + salary -----------------------------------------------------
    local_role_versions: dict[str, set[int]] = {k: set(v) for k, v in role_idx.items()}
    for cr in org.customRoles:
        local_role_versions.setdefault(cr.key, set()).add(cr.version)

    for a in agents:
        key, ver = a.role.key, a.role.version
        if key not in local_role_versions:
            issues.append(issue("ROLE_UNKNOWN", "warning", agentIds=[a.id], orgPath=path))
        elif ver not in local_role_versions[key]:
            issues.append(issue("ROLE_VERSION_UNKNOWN", "warning", agentIds=[a.id], orgPath=path))
        if not _valid_salary(a.salary):
            issues.append(issue("SALARY_INVALID", "error", agentIds=[a.id], orgPath=path))

    # -- AGENT_ORPHAN (drafting aid) ---------------------------------------
    in_dep = {d.from_ for d in deps} | {d.to for d in deps}
    has_report = {p for p in parent_of.values() if p is not None}
    for a in agents:
        if (
            a.managerId is not None
            and a.id not in in_dep
            and a.id not in has_report
        ):
            issues.append(issue("AGENT_ORPHAN", "warning", agentIds=[a.id], orgPath=path))

    # -- Recurse into children ---------------------------------------------
    for c in children:
        child_path = path + [c.organization.id]
        child_issues = validate_organization(
            c.organization, mode, catalog, _path=child_path, _catalog_index=role_idx
        )
        issues.extend(child_issues)
        if any(ci.severity == "error" for ci in child_issues):
            issues.append(
                issue("CHILD_INVALID", "error", agentIds=[c.mountAgentId], orgPath=child_path)
            )

    return issues


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for i in ids:
        if i in seen and i not in dupes:
            dupes.append(i)
        seen.add(i)
    return dupes


def _reporting_cycle_nodes(agents, agent_ids: set[str]) -> set[str]:
    manager_of = {a.id: a.managerId for a in agents}
    cyclic: set[str] = set()
    for start in agent_ids:
        seen: list[str] = []
        cur: str | None = start
        while cur is not None and cur in agent_ids:
            if cur in seen:
                i = seen.index(cur)
                cyclic.update(seen[i:])
                break
            seen.append(cur)
            cur = manager_of.get(cur)
    return cyclic


def _dependency_cycle_ids(deps, endpoint_ids: set[str]) -> set[str]:
    """Return the ids of dependencies that participate in any cycle (from → to)."""
    adj: dict[str, list[tuple[str, str]]] = {}
    for d in deps:
        if d.from_ in endpoint_ids and d.to in endpoint_ids and d.from_ != d.to:
            adj.setdefault(d.from_, []).append((d.to, d.id))

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    cyclic_dep_ids: set[str] = set()

    def dfs(node: str, path_edges: list[str]) -> None:
        color[node] = GRAY
        for nxt, dep_id in adj.get(node, []):
            c = color.get(nxt, WHITE)
            if c == GRAY:
                cyclic_dep_ids.add(dep_id)
            elif c == WHITE:
                dfs(nxt, path_edges + [dep_id])
        color[node] = BLACK

    for node in list(adj.keys()):
        if color.get(node, WHITE) == WHITE:
            dfs(node, [])
    return cyclic_dep_ids
