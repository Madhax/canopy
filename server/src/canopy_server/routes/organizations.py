"""Organization CRUD, validation, export, and import (docs §6).

This REST contract is the seam the real control plane inherits — nothing here may assume the
JSON-file store. Errors use the envelope ``{ "error": { code, message, issues? } }``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from ..catalog import get_catalog
from ..deps import get_store, now_iso
from ..ids import new_document_id
from ..migrate import UnsupportedSchemaVersion, migrate_organization
from ..models import Organization
from ..reid import reassign_ids
from ..seeds import build_seed
from ..store import JsonFileStore, NotFound
from ..validation import validate_organization

router = APIRouter()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _error(status: int, code: str, message: str, issues: list[dict] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if issues is not None:
        body["error"]["issues"] = issues
    return JSONResponse(status_code=status, content=body)


def _agent_count(org: Organization) -> int:
    return len(org.agents) + sum(_agent_count(c.organization) for c in org.childOrganizations)


def _childorg_count(org: Organization) -> int:
    return len(org.childOrganizations) + sum(
        _childorg_count(c.organization) for c in org.childOrganizations
    )


def _is_valid(org: Organization) -> bool:
    catalog = get_catalog()
    issues = validate_organization(org, "export", catalog)
    return not any(i.severity == "error" for i in issues)


def _summary(org: Organization) -> dict:
    return {
        "id": org.id,
        "name": org.name,
        "organizationType": org.organizationType,
        "agentCount": _agent_count(org),
        "childOrgCount": _childorg_count(org),
        "updatedAt": org.updatedAt,
        "valid": _is_valid(org),
    }


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "organization"


def _canonical(org: Organization) -> dict:
    """Schema-ordered dump with agents/dependencies sorted by id, recursively (docs §3.2)."""
    data = org.model_dump(by_alias=True, mode="json")

    def sort_level(node: dict) -> dict:
        node["agents"] = sorted(node.get("agents", []), key=lambda a: a["id"])
        node["dependencies"] = sorted(node.get("dependencies", []), key=lambda d: d["id"])
        for child in node.get("childOrganizations", []):
            sort_level(child["organization"])
        return node

    return sort_level(data)


def _issues_json(org: Organization, mode: str) -> list[dict]:
    catalog = get_catalog()
    return [i.to_dict() for i in validate_organization(org, mode, catalog)]


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #
class CreateOrgRequest(BaseModel):
    name: str
    organizationType: str
    seed: dict = Field(default_factory=lambda: {"kind": "blank"})


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get("/organizations")
def list_organizations(store: JsonFileStore = Depends(get_store)) -> list[dict]:
    return [_summary(o) for o in store.read_all()]


@router.post("/organizations", status_code=201)
def create_organization(
    req: CreateOrgRequest, store: JsonFileStore = Depends(get_store)
) -> Response:
    catalog = get_catalog()
    if not any(o.key == req.organizationType for o in catalog.organizationTypes):
        return _error(
            400, "UNKNOWN_ORG_TYPE", f"Unknown organizationType: {req.organizationType!r}"
        )
    try:
        agents, deps = build_seed(req.organizationType, req.seed)
    except ValueError as exc:
        return _error(400, "BAD_SEED", str(exc))

    ts = now_iso()
    org = Organization(
        id=new_document_id(),
        name=req.name,
        organizationType=req.organizationType,
        createdAt=ts,
        updatedAt=ts,
        agents=agents,
        dependencies=deps,
        # Remember the seed so the editor can "reset to original"; flag an initial auto-layout.
        meta={"seed": req.seed, "needsLayout": True},
    )
    store.write(org)
    return JSONResponse(status_code=201, content=org.model_dump(by_alias=True, mode="json"))


@router.get("/organizations/{doc_id}")
def read_organization(doc_id: str, store: JsonFileStore = Depends(get_store)) -> Response:
    try:
        org = store.read(doc_id)
    except NotFound:
        return _error(404, "NOT_FOUND", f"No organization {doc_id!r}")
    return JSONResponse(content=org.model_dump(by_alias=True, mode="json"))


@router.put("/organizations/{doc_id}")
def save_organization(
    doc_id: str, body: dict, store: JsonFileStore = Depends(get_store)
) -> Response:
    try:
        incoming = Organization.model_validate(migrate_organization(dict(body)))
    except UnsupportedSchemaVersion as exc:
        return _error(400, "UNSUPPORTED_VERSION", str(exc))
    except ValidationError as exc:
        return _error(400, "SCHEMA_INVALID", "Document failed schema validation.", exc.errors())

    if incoming.id != doc_id:
        return _error(400, "ID_MISMATCH", "Body id does not match the URL.")
    try:
        stored = store.read(doc_id)
    except NotFound:
        return _error(404, "NOT_FOUND", f"No organization {doc_id!r}")

    # Optimistic concurrency: the client must have loaded the current version.
    if body.get("updatedAt") != stored.updatedAt:
        return _error(409, "STALE_WRITE", "The stored document changed since you loaded it.")

    # Re-impose server-owned immutable fields, then bump updatedAt.
    incoming.id = stored.id
    incoming.createdAt = stored.createdAt
    incoming.kind = stored.kind
    incoming.schemaVersion = stored.schemaVersion
    incoming.updatedAt = now_iso()

    store.write(incoming)  # persists even with validation errors (draft mode never blocks saves)
    return JSONResponse(
        content={
            "document": incoming.model_dump(by_alias=True, mode="json"),
            "issues": _issues_json(incoming, "draft"),
        }
    )


@router.delete("/organizations/{doc_id}", status_code=204)
def delete_organization(doc_id: str, store: JsonFileStore = Depends(get_store)) -> Response:
    store.delete(doc_id)
    return Response(status_code=204)


@router.post("/organizations/{doc_id}/validate")
def validate_stored(
    doc_id: str,
    mode: Literal["draft", "export"] = "draft",
    store: JsonFileStore = Depends(get_store),
) -> Response:
    try:
        org = store.read(doc_id)
    except NotFound:
        return _error(404, "NOT_FOUND", f"No organization {doc_id!r}")
    return JSONResponse(content={"issues": _issues_json(org, mode)})


@router.get("/organizations/{doc_id}/export")
def export_organization(doc_id: str, store: JsonFileStore = Depends(get_store)) -> Response:
    try:
        org = store.read(doc_id)
    except NotFound:
        return _error(404, "NOT_FOUND", f"No organization {doc_id!r}")

    issues = _issues_json(org, "export")
    if any(i["severity"] == "error" for i in issues):
        return _error(422, "EXPORT_BLOCKED", "Fix validation errors before exporting.", issues)

    import json

    text = json.dumps(_canonical(org), indent=2, ensure_ascii=False) + "\n"
    filename = f"{_slugify(org.name)}.organization.json"
    return Response(
        content=text,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/organizations/import", status_code=201)
def import_organization(body: dict, store: JsonFileStore = Depends(get_store)) -> Response:
    try:
        migrated = migrate_organization(dict(body))
    except UnsupportedSchemaVersion as exc:
        return _error(400, "UNSUPPORTED_VERSION", str(exc))
    try:
        parsed = Organization.model_validate(migrated)
    except ValidationError as exc:
        return _error(400, "SCHEMA_INVALID", "Document failed schema validation.", exc.errors())

    fresh = reassign_ids(parsed)  # new ids throughout — import never collides
    ts = now_iso()
    fresh.createdAt = ts
    fresh.updatedAt = ts
    store.write(fresh)
    return JSONResponse(
        status_code=201,
        content={
            "document": fresh.model_dump(by_alias=True, mode="json"),
            "issues": _issues_json(fresh, "draft"),
        },
    )
