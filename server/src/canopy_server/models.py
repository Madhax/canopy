"""Pydantic v2 schema for Canopy documents.

Two shapes live here:

- The **catalog** (`Catalog`, `OrgType`, `CatalogRole`, `Formation`, …) — the machine-readable
  form of the domain docs, loaded from ``catalog/catalog.json``. Deliberately untouched by the
  C1 rename (roles/formations are org-model-agnostic; the layer boundary holds).
- The **team document** (`Team`, `Agent`, `Dependency`, …) — the serialized org chart, one JSON
  document per top-level team. Kind ``canopy.team`` at ``schemaVersion: 2``; v1
  ``canopy.organization`` documents import forever via ``migrate.py``.

Both mirror ``docs/org-chart-editor.md`` §3 (with its 2026-08 amendment). Unknown keys are
rejected everywhere except ``meta`` (the single forward-compat escape hatch). The Zod schema in
``ui/src/schema`` mirrors this file; the golden validation vectors keep the two honest.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 2
CATALOG_VERSION = 1

DeliverableKind = Literal["artifact", "attestation"]

# Role-group keys (roles.md section headings). Used for palette grouping + UI colors.
ROLE_GROUPS = (
    "leadership-coordination",
    "software-engineering",
    "infra-security-reliability",
    "data-ai",
    "product-design",
    "marketing-growth-content",
    "sales-customer",
    "people-recruiting",
    "finance-legal",
    "physical-operations",
    "healthcare",
    "research-education",
    "media-events",
    "professional-services",
    "nonprofit-community",
    "custom",
)

# Archetype section keys (archetypes.md §1–5).
ORG_SECTIONS = (
    "tech-enterprise",
    "physical-world",
    "knowledge-community",
    "professional-services",
    "corporate-chassis",
)


class Strict(BaseModel):
    """Base: reject unknown keys, allow population by field name or alias."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------- #
# Shared value objects
# --------------------------------------------------------------------------- #
class Deliverable(Strict):
    kind: DeliverableKind
    type: str


class Responsibility(Strict):
    duty: str
    deliverable: Deliverable


class Salary(Strict):
    perAssignmentAllowance: int
    warnThresholdPct: float = 80
    hardStop: bool = True


class Point(Strict):
    x: float
    y: float


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #
class ToolGrant(Strict):
    """One capability the platform can hand to an agent (agent-envelope.md §3.1). E3 ships the
    minimal vocabulary the MVP table needs; params are grant-level defaults, narrowable per
    role/node, never widenable."""

    key: str
    title: str
    riskClass: Literal["inert", "read", "write", "execute", "consequential"]
    minSandboxTier: int = 0
    executor: str = ""
    credentialKind: str | None = None
    governedActions: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class CatalogRole(Strict):
    key: str
    version: int = 1
    title: str
    group: str
    purpose: str
    responsibilities: list[Responsibility] = Field(default_factory=list)
    isManager: bool = False
    defaultSalary: Salary
    toolGrants: list[str] = Field(default_factory=list)  # grant keys (envelope §3.2)
    defaultRuntime: str = "loop"  # runtime kind driving this role's sessions (envelope §4)


class FormationSlot(Strict):
    slot: str
    roleKey: str


class FormationDep(Strict):
    # slot references within the formation ("from" depends on "to")
    from_: str = Field(alias="from")
    to: str
    # verify edges (`delivered`) unlock at the upstream's submission; consume edges
    # (`accepted`, default) wait for sign-off — docs/domain-model.md §Dependency.
    resolveOn: Literal["accepted", "delivered"] = "accepted"


class Formation(Strict):
    key: str
    title: str
    purpose: str
    manager: FormationSlot
    members: list[FormationSlot] = Field(default_factory=list)
    dependencies: list[FormationDep] = Field(default_factory=list)
    artifactFlow: str = ""


class OrgType(Strict):
    key: str
    title: str
    section: str
    description: str
    exampleIntent: str = ""
    rolePalette: list[str] = Field(default_factory=list)
    formations: list[str] = Field(default_factory=list)


class ConnectorSecretDecl(Strict):
    """One credential an instance of this pack must bind (connectors/01 §2)."""

    credentialKind: str
    required: bool = True
    scopesHint: list[str] = Field(default_factory=list)


class ConnectorConfigField(Strict):
    """One field of a pack's per-instance config schema. ``narrowable`` marks the axes
    roles/nodes may tighten (connectors/02 §4); non-narrowable fields are instance-fixed."""

    type: Literal["string"] = "string"
    required: bool = False
    default: str | None = None
    narrowable: bool = False


class ConnectorGrant(ToolGrant):
    """A pack-contributed ToolGrant (connectors/01 §6): merged into the one grant vocabulary
    at catalog load, plus the pack-only fields — the MCP tools it curates and the abstract
    keys it serves (connectors/01 §4, the two-layer rule)."""

    tools: list[str] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)


class ConnectorPack(Strict):
    """A connector, declared (connectors/01 §2). v1 ships ``native`` packs only — the
    platform-side executor family; ``mcp-server``/``http-api`` are later steps (05 §2)."""

    key: str
    version: int = 1
    title: str
    kind: Literal["native", "mcp-server", "http-api"] = "native"
    secrets: list[ConnectorSecretDecl] = Field(default_factory=list)
    configSchema: dict[str, ConnectorConfigField] = Field(default_factory=dict)
    grants: list[ConnectorGrant] = Field(default_factory=list)


class Catalog(Strict):
    kind: Literal["canopy.catalog"] = "canopy.catalog"
    catalogVersion: int = CATALOG_VERSION
    organizationTypes: list[OrgType] = Field(default_factory=list)
    roles: list[CatalogRole] = Field(default_factory=list)
    formations: list[Formation] = Field(default_factory=list)
    toolGrants: list[ToolGrant] = Field(default_factory=list)
    connectorPacks: list[ConnectorPack] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Team document (the actuatable chart; "Organization document" pre-C1)
# --------------------------------------------------------------------------- #
class RoleRef(Strict):
    key: str
    version: int = 1


class Extensions(Strict):
    instructions: str = ""
    responsibilities: list[Responsibility] = Field(default_factory=list)


class Agent(Strict):
    id: str
    name: str
    role: RoleRef
    managerId: str | None = None  # null => team root (THE tree encoding)
    extensions: Extensions = Field(default_factory=Extensions)
    salary: Salary
    position: Point = Field(default_factory=lambda: Point(x=0, y=0))


class Dependency(Strict):
    id: str
    from_: str = Field(alias="from")  # the dependent
    to: str  # the dependency ("from" depends on "to")
    # When the dependent unlocks: at the upstream's acceptance (consume, default)
    # or at its delivery/submission (verify) — docs/domain-model.md §Dependency.
    resolveOn: Literal["accepted", "delivered"] = "accepted"
    note: str | None = None


class CustomRole(Strict):
    key: str
    version: int = 1
    title: str
    group: str = "custom"
    purpose: str = ""
    responsibilities: list[Responsibility] = Field(default_factory=list)
    isManager: bool = False
    defaultSalary: Salary


class Team(Strict):
    kind: Literal["canopy.team"] = "canopy.team"
    schemaVersion: int = SCHEMA_VERSION
    id: str
    name: str
    # The archetype key (catalog `organizationTypes[]` — field name kept for catalog
    # compatibility; the docs call the concept TeamType post-rename).
    organizationType: str
    createdAt: str | None = None
    updatedAt: str | None = None
    agents: list[Agent] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    customRoles: list[CustomRole] = Field(default_factory=list)
    childTeams: list[ChildTeam] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ChildTeam(Strict):
    mountAgentId: str  # the PARENT agent the child team's root reports to
    team: Team


Team.model_rebuild()
