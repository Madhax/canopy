"""Re-id an entire organization tree (used by import + duplicate).

Import assigns **new ids throughout** — the document id and every nested org id, plus every agent
and dependency id — so imported/duplicated documents never collide with existing ones (docs §6).
References (managerId, dependency endpoints, mountAgentId) are remapped consistently. A dependency
endpoint may point at a mounted child org's id, so the remap covers child-org ids too.
"""

from __future__ import annotations

from .ids import new_agent_id, new_dependency_id, new_document_id
from .models import Organization


def reassign_ids(org: Organization) -> Organization:
    """Return a deep copy of ``org`` with every id freshly generated and all refs remapped."""
    fresh = org.model_copy(deep=True)
    _reassign(fresh)
    return fresh


def _reassign(org: Organization) -> None:
    org.id = new_document_id()

    # Build id remap for agents and mounted child orgs (both can be dependency endpoints).
    id_map: dict[str, str] = {}
    for agent in org.agents:
        id_map[agent.id] = new_agent_id()
    for child in org.childOrganizations:
        # a child org participates in sibling dependencies via its (old) org id
        id_map[child.organization.id] = ""  # filled after recursion assigns the new id

    # Apply new agent ids + remap managerId.
    for agent in org.agents:
        old = agent.id
        agent.id = id_map[old]
    for agent in org.agents:
        if agent.managerId is not None and agent.managerId in id_map:
            agent.managerId = id_map[agent.managerId]

    # Recurse into children first so their new org ids are known, then remap mount + endpoints.
    for child in org.childOrganizations:
        old_child_org_id = child.organization.id
        if child.mountAgentId in id_map:
            child.mountAgentId = id_map[child.mountAgentId]
        _reassign(child.organization)
        id_map[old_child_org_id] = child.organization.id

    # Remap dependency endpoints + assign fresh dependency ids.
    for dep in org.dependencies:
        dep.id = new_dependency_id()
        if dep.from_ in id_map and id_map[dep.from_]:
            dep.from_ = id_map[dep.from_]
        if dep.to in id_map and id_map[dep.to]:
            dep.to = id_map[dep.to]
