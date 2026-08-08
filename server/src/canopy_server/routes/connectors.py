"""Connector instances — the operator API behind the builder's connector pills
(docs/design/builder-connectors.md §3).

Same posture as profiles/secrets: org-scoped operator data, secrets write-only (values arrive
in a ``secrets`` field, land in the Secret Store, and are returned as ids — never plaintext),
every mutation activity-logged, effect at next assignment intake plus fail-closed per call.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..catalog import get_catalog

# Imported at module scope ON PURPOSE: routers load at app import, which registers the
# connector_instance schema before any Db is constructed (the dp.py→engine precedent).
from ..connectors import ConnectorInstance
from ..deps import (
    get_activity,
    get_connector_store,
    get_github_client,
    get_secret_store,
    get_store,
)
from ..github_client import GitHubError

router = APIRouter()


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _require_org(store, org_id: str) -> JSONResponse | None:
    if not store.exists(org_id):
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    return None


class InstanceBody(BaseModel):
    packKey: str
    name: str
    config: dict[str, str] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # kind -> PLAINTEXT, write-only
    enabledGrants: list[str] = Field(default_factory=list)
    nodeLinks: list[str] | None = None


class InstancePatch(BaseModel):
    name: str | None = None
    config: dict[str, str] | None = None
    secrets: dict[str, str] | None = None
    enabledGrants: list[str] | None = None
    # nodeLinks is tri-state (org-wide None / scoped list) — a sentinel distinguishes
    # "not sent" from "set to org-wide".
    nodeLinks: list[str] | None = Field(default=None)
    linkScope: str | None = None  # "org" | "nodes" | None(untouched)
    enabled: bool | None = None


def _validate(catalog, store, org_id: str, pack_key: str, config: dict, grants: list[str],
              node_links: list[str] | None) -> JSONResponse | None:
    pack = next((p for p in catalog.connectorPacks if p.key == pack_key), None)
    if pack is None:
        return _error(400, "BAD_PACK", f"unknown connector pack {pack_key!r}")
    # Config completeness is deliberately NOT checked here: the builder flow is drop →
    # configure → verify (builder-connectors-ux.md §2.2) — an incomplete instance is parked
    # and inert; Verify and actuation readiness are where it surfaces.
    pack_grant_keys = {g.key for g in pack.grants}
    for gk in grants:
        if gk not in pack_grant_keys:
            return _error(400, "BAD_GRANT", f"{gk!r} is not a grant of pack {pack_key!r}")
    if node_links:
        org = store.read(org_id)
        node_ids = {a.id for a in getattr(org, "agents", [])}
        for nid in node_links:
            if nid not in node_ids:
                return _error(400, "BAD_NODE", f"unknown node {nid!r}")
    return None


def _store_secrets(secret_store, org_id: str, name: str, plain: dict[str, str]) -> dict[str, str]:
    return {
        kind: secret_store.create(org_id, f"{name}:{kind}", value).id
        for kind, value in plain.items() if value
    }


@router.get("/organizations/{org_id}/connector-packs")
def list_packs(org_id: str, store=Depends(get_store)) -> Any:
    """The palette's source: catalog packs with their grants (builder-connectors-ux.md §2.1)."""
    if (err := _require_org(store, org_id)) is not None:
        return err
    return {"packs": [p.model_dump() for p in get_catalog().connectorPacks]}


@router.get("/organizations/{org_id}/connectors")
def list_instances(
    org_id: str, store=Depends(get_store), connectors=Depends(get_connector_store)
) -> Any:
    if (err := _require_org(store, org_id)) is not None:
        return err
    return {"instances": [i.model_dump() for i in connectors.list(org_id)]}


@router.post("/organizations/{org_id}/connectors", status_code=201)
def create_instance(
    org_id: str, body: InstanceBody,
    store=Depends(get_store), connectors=Depends(get_connector_store),
    secret_store=Depends(get_secret_store), activity=Depends(get_activity),
) -> Any:
    if (err := _require_org(store, org_id)) is not None:
        return err
    catalog = get_catalog()
    if (err := _validate(catalog, store, org_id, body.packKey, body.config,
                         body.enabledGrants, body.nodeLinks)) is not None:
        return err
    bindings = _store_secrets(secret_store, org_id, body.name or body.packKey, body.secrets)
    inst: ConnectorInstance = connectors.create(
        org_id, body.packKey, body.name, config=body.config,
        secret_bindings=bindings, enabled_grants=body.enabledGrants,
        node_links=body.nodeLinks,
    )
    activity.log("operator", "connector.created", org_id=org_id,
                 subject_ids=[inst.id], payload={"pack": body.packKey, "name": body.name})
    return inst.model_dump()


@router.put("/organizations/{org_id}/connectors/{instance_id}")
def update_instance(
    org_id: str, instance_id: str, body: InstancePatch,
    store=Depends(get_store), connectors=Depends(get_connector_store),
    secret_store=Depends(get_secret_store), activity=Depends(get_activity),
) -> Any:
    if (err := _require_org(store, org_id)) is not None:
        return err
    current = connectors.get(instance_id)
    if current is None or current.organizationId != org_id:
        return _error(404, "NOT_FOUND", f"No connector instance {instance_id!r}")
    catalog = get_catalog()
    changes: dict[str, Any] = {}
    if body.name is not None:
        changes["name"] = body.name
    if body.config is not None:
        changes["config"] = body.config
    if body.enabledGrants is not None:
        changes["enabledGrants"] = body.enabledGrants
    if body.linkScope == "org":
        changes["nodeLinks"] = None
    elif body.linkScope == "nodes":
        changes["nodeLinks"] = body.nodeLinks or []
    if body.enabled is not None:
        changes["enabled"] = body.enabled
    if body.secrets:
        merged = dict(current.secretBindings)
        merged.update(_store_secrets(secret_store, org_id, current.name, body.secrets))
        changes["secretBindings"] = merged
    if (err := _validate(catalog, store, org_id, current.packKey,
                         changes.get("config", current.config),
                         changes.get("enabledGrants", current.enabledGrants),
                         changes.get("nodeLinks", current.nodeLinks))) is not None:
        return err
    inst = connectors.update(instance_id, changes)
    activity.log("operator", "connector.updated", org_id=org_id, subject_ids=[instance_id],
                 payload={k: v for k, v in changes.items() if k != "secretBindings"})
    return inst.model_dump()


@router.delete("/organizations/{org_id}/connectors/{instance_id}", status_code=204)
def delete_instance(
    org_id: str, instance_id: str,
    store=Depends(get_store), connectors=Depends(get_connector_store),
    activity=Depends(get_activity),
):
    if (err := _require_org(store, org_id)) is not None:
        return err
    current = connectors.get(instance_id)
    if current is None or current.organizationId != org_id:
        return _error(404, "NOT_FOUND", f"No connector instance {instance_id!r}")
    connectors.delete(instance_id)
    activity.log("operator", "connector.deleted", org_id=org_id, subject_ids=[instance_id],
                 payload={"pack": current.packKey, "name": current.name})
    return None


@router.post("/organizations/{org_id}/connectors/{instance_id}/verify")
def verify_instance(
    org_id: str, instance_id: str,
    store=Depends(get_store), connectors=Depends(get_connector_store),
    secret_store=Depends(get_secret_store), activity=Depends(get_activity),
    github=Depends(get_github_client),
) -> Any:
    """Health check (builder-connectors-ux.md §2.3): credential presence, then a reachability
    probe. Misconfiguration surfaces here, at bind time, not mid-assignment."""
    if (err := _require_org(store, org_id)) is not None:
        return err
    inst = connectors.get(instance_id)
    if inst is None or inst.organizationId != org_id:
        return _error(404, "NOT_FOUND", f"No connector instance {instance_id!r}")
    catalog = get_catalog()
    pack = next((p for p in catalog.connectorPacks if p.key == inst.packKey), None)
    result: dict[str, Any] = {"ok": True, "checks": []}

    def check(name: str, ok: bool, detail: str = ""):
        result["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            result["ok"] = False

    for field, decl in ((pack.configSchema if pack else {}) or {}).items():
        if decl.required:
            check(f"config:{field}", bool(inst.config.get(field)),
                  "" if inst.config.get(field) else "required field is empty")
    for decl in (pack.secrets if pack else []):
        bound = decl.credentialKind in inst.secretBindings
        present = bound and secret_store.get_meta(inst.secretBindings[decl.credentialKind])
        check(f"secret:{decl.credentialKind}", bool(present),
              "" if present else "credential not bound")
    if inst.packKey == "github" and result["ok"]:
        token = secret_store.reveal(inst.secretBindings.get("scm-token", ""))
        try:
            repo = github.get_repo(token or "", inst.config.get("owner", ""),
                                   inst.config.get("repo", ""))
            check("repo", True, repo.get("full_name", ""))
        except GitHubError as exc:
            check("repo", False, str(exc))
    elif inst.packKey == "local-git":
        from pathlib import Path
        src = Path(inst.config.get("source", ""))
        check("source", (src / ".git").exists(),
              "" if (src / ".git").exists() else f"not a git repository: {src}")
    activity.log("operator", "connector.verify", org_id=org_id, subject_ids=[instance_id],
                 payload={"ok": result["ok"]})
    return result
