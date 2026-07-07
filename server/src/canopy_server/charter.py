"""Charter compilation — what an agent is told at boot (agent-runtime.md §1, control-plane.md §2).

The charter is the *only* thing an agent knows about the org: its own identity, its compiled role
instructions (RoleTemplate base + node extensions + profile preamble), its manager and reports,
its salary numbers, and its workspace layout. The runtime never reads the Organization document —
so the control plane is the single source of truth and the agent is dumb and replaceable
(topology.md §1).
"""

from __future__ import annotations

from pydantic import BaseModel

from .models import Agent, Catalog, Organization, Salary


class WorkspaceLayout(BaseModel):
    brief: str = "brief"
    work: str = "work"
    out: str = "out"
    memory: str = "memory.json"


class Charter(BaseModel):
    nodeId: str
    orgId: str
    actuationId: str
    orgPath: list[str]
    displayName: str
    roleKey: str
    isManager: bool
    instructions: str
    managerNodeId: str | None
    reportNodeIds: list[str]
    salary: Salary
    workspaceLayout: WorkspaceLayout = WorkspaceLayout()


def org_at_path(top: Organization, org_path: list[str]) -> Organization | None:
    org = top
    for child_id in org_path:
        nxt = next(
            (c.organization for c in org.childOrganizations if c.organization.id == child_id),
            None,
        )
        if nxt is None:
            return None
        org = nxt
    return org


def _role_and_manager_flag(org: Organization, agent: Agent, catalog: Catalog | None) -> tuple:
    role = None
    if catalog:
        role = next((r for r in catalog.roles if r.key == agent.role.key), None)
    if role is None:
        role = next((r for r in org.customRoles if r.key == agent.role.key), None)
    is_manager = bool(getattr(role, "isManager", False))
    return role, is_manager


def _compile_instructions(role, agent: Agent, profile_preamble: str) -> str:
    parts: list[str] = []
    if role is not None:
        parts.append(f"You are a {role.title}.")
        if role.purpose:
            parts.append(role.purpose)
        if role.responsibilities:
            lines = ["Your standing responsibilities:"]
            for r in role.responsibilities:
                lines.append(f"- {r.duty} → {r.deliverable.kind}: {r.deliverable.type}")
            parts.append("\n".join(lines))
    else:
        parts.append(f"You act as: {agent.role.key}.")

    ext = agent.extensions
    if ext.instructions.strip():
        parts.append(ext.instructions.strip())
    if ext.responsibilities:
        lines = ["Additional responsibilities for this engagement:"]
        for r in ext.responsibilities:
            lines.append(f"- {r.duty} → {r.deliverable.kind}: {r.deliverable.type}")
        parts.append("\n".join(lines))

    if profile_preamble.strip():
        parts.append(profile_preamble.strip())
    return "\n\n".join(parts)


def compile_charter(
    top: Organization,
    org_path: list[str],
    node_id: str,
    *,
    catalog: Catalog | None,
    actuation_id: str,
    profile_preamble: str = "",
) -> Charter | None:
    org = org_at_path(top, org_path)
    if org is None:
        return None
    agent = next((a for a in org.agents if a.id == node_id), None)
    if agent is None:
        return None

    role, is_manager = _role_and_manager_flag(org, agent, catalog)
    report_ids = [a.id for a in org.agents if a.managerId == node_id]
    # A mounted child org's root "looks like any other report" (domain: sub-org opacity).
    report_ids += [
        c.organization.id for c in org.childOrganizations if c.mountAgentId == node_id
    ]

    return Charter(
        nodeId=node_id,
        orgId=org.id,
        actuationId=actuation_id,
        orgPath=org_path,
        displayName=agent.name,
        roleKey=agent.role.key,
        isManager=is_manager or len(report_ids) > 0,
        instructions=_compile_instructions(role, agent, profile_preamble),
        managerNodeId=agent.managerId,
        reportNodeIds=report_ids,
        salary=agent.salary,
    )
