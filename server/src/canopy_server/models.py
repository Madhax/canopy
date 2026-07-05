"""Pydantic v2 schema for Canopy documents.

Two shapes live here:

- The **catalog** (`Catalog`, `OrgType`, `CatalogRole`, `Formation`, …) — the machine-readable
  form of the domain docs, loaded from ``catalog/catalog.json``.
- The **organization document** (`Organization`, `Agent`, `Dependency`, …) — the serialized
  org chart, one JSON document per top-level organization.

Both mirror ``docs/org-chart-editor.md`` §3. Unknown keys are rejected everywhere except ``meta``
(the single forward-compat escape hatch). The Zod schema in ``ui/src/schema`` mirrors this file;
the golden validation vectors keep the two honest.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1
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
class CatalogRole(Strict):
    key: str
    version: int = 1
    title: str
    group: str
    purpose: str
    responsibilities: list[Responsibility] = Field(default_factory=list)
    isManager: bool = False
    defaultSalary: Salary


class FormationSlot(Strict):
    slot: str
    roleKey: str


class FormationDep(Strict):
    # slot references within the formation ("from" depends on "to")
    from_: str = Field(alias="from")
    to: str


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


class Catalog(Strict):
    kind: Literal["canopy.catalog"] = "canopy.catalog"
    catalogVersion: int = CATALOG_VERSION
    organizationTypes: list[OrgType] = Field(default_factory=list)
    roles: list[CatalogRole] = Field(default_factory=list)
    formations: list[Formation] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Organization document
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
    managerId: str | None = None  # null => org root (THE tree encoding)
    extensions: Extensions = Field(default_factory=Extensions)
    salary: Salary
    position: Point = Field(default_factory=lambda: Point(x=0, y=0))


class Dependency(Strict):
    id: str
    from_: str = Field(alias="from")  # the dependent
    to: str  # the dependency ("from" depends on "to")
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


class Organization(Strict):
    kind: Literal["canopy.organization"] = "canopy.organization"
    schemaVersion: int = SCHEMA_VERSION
    id: str
    name: str
    organizationType: str
    createdAt: str | None = None
    updatedAt: str | None = None
    agents: list[Agent] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    customRoles: list[CustomRole] = Field(default_factory=list)
    childOrganizations: list[ChildOrganization] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ChildOrganization(Strict):
    mountAgentId: str  # the PARENT agent the child org's root reports to
    organization: Organization


Organization.model_rebuild()
