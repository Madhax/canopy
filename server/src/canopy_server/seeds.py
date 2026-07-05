"""Seed construction for new organizations, plus the formation-stamp primitive.

A new org can be seeded three ways (docs §6, §7.3):

- ``blank``      — no agents (the first placed agent becomes the root).
- ``root``       — a single root agent of a chosen role.
- ``formation``  — a pre-wired formation subtree whose manager becomes the root.

The formation stamp resolves the formation's slot-based dependency wiring to concrete agent ids;
the UI performs the same stamp client-side when dropping a formation onto the canvas.
"""

from __future__ import annotations

from .catalog import get_catalog
from .ids import new_agent_id, new_dependency_id
from .models import (
    Agent,
    Catalog,
    CatalogRole,
    Dependency,
    Point,
    RoleRef,
    Salary,
)

_MANAGER_X = 400.0
_MANAGER_Y = 80.0
_MEMBER_Y = 300.0
_MEMBER_DX = 240.0


def role_by_key(catalog: Catalog, key: str) -> CatalogRole | None:
    for r in catalog.roles:
        if r.key == key:
            return r
    return None


def agent_from_role(
    catalog: Catalog,
    role_key: str,
    manager_id: str | None,
    position: Point,
    name: str | None = None,
) -> Agent:
    role = role_by_key(catalog, role_key)
    salary = role.defaultSalary if role else Salary(perAssignmentAllowance=120000)
    title = role.title if role else role_key
    return Agent(
        id=new_agent_id(),
        name=name or title,
        role=RoleRef(key=role_key, version=role.version if role else 1),
        managerId=manager_id,
        salary=salary.model_copy(deep=True),
        position=position,
    )


def stamp_formation(
    catalog: Catalog,
    formation_key: str,
    manager_manager_id: str | None = None,
    origin: Point | None = None,
) -> tuple[list[Agent], list[Dependency]]:
    """Materialize a formation subtree. Returns (agents, dependencies) with fresh ids.

    ``manager_manager_id`` is the id the formation's manager reports to (``None`` => the manager
    becomes an org root). ``origin`` positions the manager node; members fan out below it.
    """
    formation = next((f for f in catalog.formations if f.key == formation_key), None)
    if formation is None:
        raise ValueError(f"unknown formation: {formation_key}")

    ox = origin.x if origin else _MANAGER_X
    oy = origin.y if origin else _MANAGER_Y

    manager = agent_from_role(
        catalog, formation.manager.roleKey, manager_manager_id, Point(x=ox, y=oy)
    )
    slot_to_agent: dict[str, str] = {formation.manager.slot: manager.id}
    agents: list[Agent] = [manager]

    n = len(formation.members)
    total_w = (n - 1) * _MEMBER_DX
    start_x = ox - total_w / 2
    for i, member in enumerate(formation.members):
        pos = Point(x=start_x + i * _MEMBER_DX, y=oy + _MEMBER_Y)
        a = agent_from_role(catalog, member.roleKey, manager.id, pos)
        slot_to_agent[member.slot] = a.id
        agents.append(a)

    deps: list[Dependency] = []
    for d in formation.dependencies:
        frm = slot_to_agent.get(d.from_)
        to = slot_to_agent.get(d.to)
        if frm and to:
            deps.append(Dependency(id=new_dependency_id(), from_=frm, to=to))
    return agents, deps


def build_seed(
    organization_type: str,
    seed: dict,
) -> tuple[list[Agent], list[Dependency]]:
    catalog = get_catalog()
    kind = (seed or {}).get("kind", "blank")

    if kind == "blank":
        return [], []

    if kind == "root":
        role_key = seed.get("roleKey") or _default_root_role(catalog, organization_type)
        agent = agent_from_role(catalog, role_key, None, Point(x=_MANAGER_X, y=_MANAGER_Y))
        return [agent], []

    if kind == "formation":
        formation_key = seed.get("formationKey")
        if not formation_key:
            raise ValueError("formation seed requires formationKey")
        return stamp_formation(catalog, formation_key, manager_manager_id=None)

    raise ValueError(f"unknown seed kind: {kind!r}")


def _default_root_role(catalog: Catalog, organization_type: str) -> str:
    """The archetype's leadership role (first manager in its palette), else chief-executive."""
    org = next((o for o in catalog.organizationTypes if o.key == organization_type), None)
    if org:
        managers = {r.key for r in catalog.roles if r.isManager}
        for rk in org.rolePalette:
            if rk in managers:
                return rk
        if org.rolePalette:
            return org.rolePalette[0]
    return "chief-executive"
