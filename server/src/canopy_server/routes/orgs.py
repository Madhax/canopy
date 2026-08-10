"""Organizations + the portfolio home (design/organizations/, milestone C1).

The Organization is the umbrella above Teams: identity, theme, priority class, budget — never
actuated, never a chart (invariant 12). C1 ships the entity CRUD, the read-only portfolio
aggregate, and the move-team custody transfer; budgets are stored now and enforced at C5;
capacity headlines join the aggregate at C3.

Old ``/api/organizations…`` paths (the pre-rename chart CRUD) answer ``410 Gone`` with the new
``/api/teams…`` path in the body for two releases — see :func:`gone` below.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..deps import get_activity, get_actuator, get_org_store, get_store
from ..orgs import OrgError, OrgNotEmpty, OrgNotFound, valid_org_key
from ..store import NotFound

router = APIRouter()


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _org_json(org) -> dict:
    return org.model_dump(mode="json")


def _team_ids_of(store, org_id: str) -> list[str]:
    ids = getattr(store, "ids_in_organization", None)
    return ids(org_id) if ids else []


# --------------------------------------------------------------------------- #
# Organization CRUD
# --------------------------------------------------------------------------- #
class CreateOrgRequest(BaseModel):
    key: str
    name: str
    purpose: str = ""
    theme: dict[str, Any] = Field(default_factory=dict)
    priorityClass: str = "batch"
    budget: dict[str, Any] = Field(default_factory=dict)


class UpdateOrgRequest(BaseModel):
    name: str | None = None
    purpose: str | None = None
    theme: dict[str, Any] | None = None
    priorityClass: str | None = None
    budget: dict[str, Any] | None = None


@router.get("/orgs")
def list_orgs(orgs=Depends(get_org_store), store=Depends(get_store)) -> list[dict]:
    return [
        {**_org_json(o), "teamIds": _team_ids_of(store, o.id)} for o in orgs.list()
    ]


@router.post("/orgs", status_code=201)
def create_org(req: CreateOrgRequest, orgs=Depends(get_org_store)):
    if not valid_org_key(req.key):
        return _error(400, "BAD_ORG_KEY", f"Invalid organization key: {req.key!r}")
    if orgs.get_by_key(req.key) is not None:
        return _error(409, "ORG_KEY_TAKEN", f"An organization with key {req.key!r} exists.")
    org = orgs.create(
        key=req.key,
        name=req.name,
        purpose=req.purpose,
        theme=req.theme,
        priority_class=req.priorityClass,
        budget=req.budget,
    )
    return JSONResponse(status_code=201, content=_org_json(org))


@router.get("/orgs/{org_id}")
def read_org(org_id: str, orgs=Depends(get_org_store), store=Depends(get_store)):
    try:
        org = orgs.get(org_id)
    except OrgNotFound:
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    return {**_org_json(org), "teamIds": _team_ids_of(store, org_id)}


@router.put("/orgs/{org_id}")
def update_org(org_id: str, req: UpdateOrgRequest, orgs=Depends(get_org_store)):
    try:
        org = orgs.update(
            org_id,
            name=req.name,
            purpose=req.purpose,
            theme=req.theme,
            priority_class=req.priorityClass,
            budget=req.budget,
        )
    except OrgNotFound:
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    return _org_json(org)


@router.put("/orgs/{org_id}/budget")
def update_org_budget(org_id: str, budget: dict, orgs=Depends(get_org_store)):
    try:
        org = orgs.update(org_id, budget=budget)
    except OrgNotFound:
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    return _org_json(org)


@router.delete("/orgs/{org_id}")
def delete_org(org_id: str, orgs=Depends(get_org_store), store=Depends(get_store)):
    try:
        if _team_ids_of(store, org_id):
            return _error(
                409, "ORG_NOT_EMPTY", "Move or delete this organization's teams first."
            )
        orgs.delete(org_id)
    except OrgNotFound:
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    except (OrgNotEmpty, OrgError) as exc:
        return _error(409, "ORG_DELETE_BLOCKED", str(exc))
    return JSONResponse(status_code=204, content=None)


# --------------------------------------------------------------------------- #
# Portfolio home (read-only cards, 05-ux-portfolio §2) + move-team flow
# --------------------------------------------------------------------------- #
@router.get("/portfolio")
def portfolio(
    orgs=Depends(get_org_store), store=Depends(get_store), actuator=Depends(get_actuator)
) -> dict:
    from .teams import _summary  # late import to avoid a router import cycle

    teams_by_org: dict[str, list[dict]] = {}
    for team in store.read_all():
        card = _summary(team)
        current = actuator.get_current(team.id)
        card["actuation"] = getattr(current, "state", None) if current else None
        org_id = card.get("organizationId") or getattr(store, "default_org_id", None)
        teams_by_org.setdefault(org_id, []).append(card)
    return {
        "organizations": [
            {**_org_json(o), "teams": teams_by_org.get(o.id, [])} for o in orgs.list()
        ]
    }


class MoveTeamRequest(BaseModel):
    organizationId: str


@router.post("/teams/{team_id}/move")
def move_team(
    team_id: str,
    req: MoveTeamRequest,
    orgs=Depends(get_org_store),
    store=Depends(get_store),
    actuator=Depends(get_actuator),
    activity=Depends(get_activity),
):
    """Custody transfer (01 §3): explicit, blocked while actuated, audited."""
    mover = getattr(store, "move_to_organization", None)
    if mover is None:
        return _error(409, "BACKEND_UNSUPPORTED", "Team moves need the sqlite backend.")
    try:
        target = orgs.get(req.organizationId)
    except OrgNotFound:
        return _error(404, "NOT_FOUND", f"No organization {req.organizationId!r}")
    if actuator.get_current(team_id) is not None:
        return _error(409, "ACTUATION_LIVE", "Deactuate this team before moving it.")
    try:
        previous = store.organization_of(team_id)
        prev_key = orgs.get(previous).key if previous else None
        mover(team_id, target.id)
    except NotFound:
        return _error(404, "NOT_FOUND", f"No team {team_id!r}")
    except OrgNotFound:
        prev_key = None
        mover(team_id, target.id)
    # The filesystem home rides the custody transfer (07 §2.5); safe — not actuated.
    if prev_key and prev_key != target.key:
        import shutil

        from ..config import get_data_dir

        old_home = get_data_dir() / "orgs" / prev_key / "teams" / team_id
        new_home = get_data_dir() / "orgs" / target.key / "teams" / team_id
        if old_home.is_dir() and not new_home.exists():
            new_home.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_home), str(new_home))
    activity.log(
        "operator",
        "team.moved",
        team_id=team_id,
        payload={"from": previous, "to": target.id, "toKey": target.key},
    )
    return {"teamId": team_id, "organizationId": target.id}


# --------------------------------------------------------------------------- #
# The old chart-CRUD root: 410 Gone with the new path (07 §3, two releases)
# --------------------------------------------------------------------------- #
@router.api_route(
    "/organizations/{rest:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
@router.api_route(
    "/organizations", methods=["GET", "POST"], include_in_schema=False
)
def gone(rest: str = "") -> JSONResponse:
    new_path = f"/api/teams/{rest}".rstrip("/")
    return JSONResponse(
        status_code=410,
        content={
            "error": {
                "code": "MOVED_TO_TEAMS",
                "message": "Organizations (chart sense) are Teams since C1"
                " (design/organizations/01). Use the new path.",
                "newPath": new_path,
            }
        },
    )
