"""Re-id an entire team tree (used by import + duplicate).

Import assigns **new ids throughout** — the document id and every nested team id, plus every agent
and dependency id — so imported/duplicated documents never collide with existing ones (docs §6).
References (managerId, dependency endpoints, mountAgentId) are remapped consistently. A dependency
endpoint may point at a mounted child team's id, so the remap covers child-team ids too.
"""

from __future__ import annotations

from .ids import new_agent_id, new_dependency_id, new_document_id
from .models import Team


def reassign_ids(team: Team) -> Team:
    """Return a deep copy of ``team`` with every id freshly generated and all refs remapped."""
    fresh = team.model_copy(deep=True)
    _reassign(fresh)
    return fresh


def _reassign(team: Team) -> None:
    team.id = new_document_id()

    # Build id remap for agents and mounted child teams (both can be dependency endpoints).
    id_map: dict[str, str] = {}
    for agent in team.agents:
        id_map[agent.id] = new_agent_id()
    for child in team.childTeams:
        # a child team participates in sibling dependencies via its (old) team id
        id_map[child.team.id] = ""  # filled after recursion assigns the new id

    # Apply new agent ids + remap managerId.
    for agent in team.agents:
        old = agent.id
        agent.id = id_map[old]
    for agent in team.agents:
        if agent.managerId is not None and agent.managerId in id_map:
            agent.managerId = id_map[agent.managerId]

    # Recurse into children first so their new team ids are known, then remap mount + endpoints.
    for child in team.childTeams:
        old_child_team_id = child.team.id
        if child.mountAgentId in id_map:
            child.mountAgentId = id_map[child.mountAgentId]
        _reassign(child.team)
        id_map[old_child_team_id] = child.team.id

    # Remap dependency endpoints + assign fresh dependency ids.
    for dep in team.dependencies:
        dep.id = new_dependency_id()
        if dep.from_ in id_map and id_map[dep.from_]:
            dep.from_ = id_map[dep.from_]
        if dep.to in id_map and id_map[dep.to]:
            dep.to = id_map[dep.to]
