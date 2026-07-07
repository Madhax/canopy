"""Profiles, bindings, and secrets — the operator-facing configuration API (control-plane.md §9).

These attach the AI configuration to a chart without touching the Organization document
(agent-profile.md): profiles are the reusable brains, bindings pin a profile to a node, secrets
are the encrypted keys profiles reference. Secrets are **write-only** here — create / rotate /
delete return metadata only; no route ever returns a key's plaintext (invariant 10).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..deps import get_gateway, get_profile_store, get_secret_store, get_store
from ..profiles import ProfileParams, Provider

router = APIRouter()


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _require_org(store, org_id: str) -> JSONResponse | None:
    if not store.exists(org_id):
        return _error(404, "NOT_FOUND", f"No organization {org_id!r}")
    return None


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #
class ProfileBody(BaseModel):
    name: str
    provider: Provider
    model: str
    endpoint: str | None = None
    apiKeySecretId: str | None = None
    params: ProfileParams = Field(default_factory=ProfileParams)
    systemPreamble: str = ""


class ProfilePatch(BaseModel):
    name: str | None = None
    provider: Provider | None = None
    model: str | None = None
    endpoint: str | None = None
    apiKeySecretId: str | None = None
    params: ProfileParams | None = None
    systemPreamble: str | None = None


class BindingBody(BaseModel):
    agentNodeId: str
    profileId: str
    orgPath: list[str] = Field(default_factory=list)


class SecretBody(BaseModel):
    name: str
    value: str


class SecretRotate(BaseModel):
    value: str


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #
@router.get("/organizations/{org_id}/profiles")
def list_profiles(
    org_id: str, profiles=Depends(get_profile_store), store=Depends(get_store)
) -> Any:
    if (err := _require_org(store, org_id)) is not None:
        return err
    return [p.model_dump() for p in profiles.list_profiles(org_id)]


@router.post("/organizations/{org_id}/profiles", status_code=201)
def create_profile(
    org_id: str, body: ProfileBody, profiles=Depends(get_profile_store), store=Depends(get_store)
) -> Any:
    if (err := _require_org(store, org_id)) is not None:
        return err
    p = profiles.create_profile(
        org_id,
        name=body.name,
        provider=body.provider,
        model=body.model,
        endpoint=body.endpoint,
        api_key_secret_id=body.apiKeySecretId,
        params=body.params,
        system_preamble=body.systemPreamble,
    )
    return JSONResponse(status_code=201, content=p.model_dump())


@router.put("/organizations/{org_id}/profiles/{profile_id}")
def update_profile(
    org_id: str, profile_id: str, body: ProfilePatch, profiles=Depends(get_profile_store)
) -> Any:
    changes = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "params" in changes:
        changes["params"] = ProfileParams.model_validate(changes["params"])
    updated = profiles.update_profile(profile_id, changes)
    if updated is None:
        return _error(404, "NOT_FOUND", f"No profile {profile_id!r}")
    return updated.model_dump()


@router.delete("/organizations/{org_id}/profiles/{profile_id}", status_code=204)
def delete_profile(org_id: str, profile_id: str, profiles=Depends(get_profile_store)):
    profiles.delete_profile(profile_id)
    return JSONResponse(status_code=204, content=None)


@router.post("/organizations/{org_id}/profiles/{profile_id}/validate")
async def validate_profile(org_id: str, profile_id: str, gateway=Depends(get_gateway)) -> Any:
    """Live-check: one cheap provider ping (agent-profile.md §3). Mock always passes."""
    result = await gateway.validate_profile(profile_id)
    return result.model_dump()


# --------------------------------------------------------------------------- #
# Bindings
# --------------------------------------------------------------------------- #
@router.get("/organizations/{org_id}/bindings")
def list_bindings(org_id: str, profiles=Depends(get_profile_store)) -> Any:
    return [b.model_dump() for b in profiles.list_bindings(org_id)]


@router.put("/organizations/{org_id}/bindings")
def set_binding(org_id: str, body: BindingBody, profiles=Depends(get_profile_store)) -> Any:
    if profiles.get_profile(body.profileId) is None:
        return _error(422, "PROFILE_DANGLING", f"No profile {body.profileId!r}")
    b = profiles.set_binding(org_id, body.agentNodeId, body.profileId, body.orgPath)
    return b.model_dump()


@router.delete("/organizations/{org_id}/bindings/{agent_node_id}", status_code=204)
def delete_binding(
    org_id: str, agent_node_id: str, orgPath: str = "", profiles=Depends(get_profile_store)
):
    path = [seg for seg in orgPath.split(",") if seg]
    profiles.delete_binding(org_id, agent_node_id, path)
    return JSONResponse(status_code=204, content=None)


# --------------------------------------------------------------------------- #
# Secrets (write-only)
# --------------------------------------------------------------------------- #
@router.get("/organizations/{org_id}/secrets")
def list_secrets(org_id: str, secrets=Depends(get_secret_store)) -> Any:
    return [s.model_dump() for s in secrets.list(org_id)]


@router.post("/organizations/{org_id}/secrets", status_code=201)
def create_secret(
    org_id: str, body: SecretBody, secrets=Depends(get_secret_store), store=Depends(get_store)
) -> Any:
    if (err := _require_org(store, org_id)) is not None:
        return err
    meta = secrets.create(org_id, body.name, body.value)
    return JSONResponse(status_code=201, content=meta.model_dump())


@router.put("/organizations/{org_id}/secrets/{secret_id}")
def rotate_secret(
    org_id: str, secret_id: str, body: SecretRotate, secrets=Depends(get_secret_store)
) -> Any:
    meta = secrets.rotate(secret_id, body.value)
    if meta is None:
        return _error(404, "NOT_FOUND", f"No secret {secret_id!r}")
    return meta.model_dump()


@router.delete("/organizations/{org_id}/secrets/{secret_id}", status_code=204)
def delete_secret(org_id: str, secret_id: str, secrets=Depends(get_secret_store)):
    secrets.delete(secret_id)
    return JSONResponse(status_code=204, content=None)
