// Build a nested child Organization document client-side. Child orgs aren't separately addressable
// on the server (docs §6) — they're created in the browser and saved as part of the top document.
import type { Catalog, OrgType } from "../schema/catalog";
import type { Agent, Dependency, OrganizationDoc, Salary } from "../schema/organization";
import { buildFormationSubtree } from "./formation";
import { newAgentId } from "./ids";

export type ChildSeed =
  | { kind: "blank" }
  | { kind: "root"; roleKey: string }
  | { kind: "formation"; formationKey: string };

function agentFromRole(catalog: Catalog, roleKey: string): Agent {
  const role = catalog.roles.find((r) => r.key === roleKey);
  const salary: Salary = role
    ? { ...role.defaultSalary }
    : { perAssignmentAllowance: 120000, warnThresholdPct: 80, hardStop: true };
  return {
    id: newAgentId(),
    name: role?.title ?? roleKey,
    role: { key: roleKey, version: role?.version ?? 1 },
    managerId: null,
    extensions: { instructions: "", responsibilities: [] },
    salary,
    position: { x: 400, y: 80 },
  };
}

export function defaultRootRole(catalog: Catalog, orgType: OrgType | undefined): string {
  const managers = new Set(catalog.roles.filter((r) => r.isManager).map((r) => r.key));
  return (
    orgType?.rolePalette.find((k) => managers.has(k)) ?? orgType?.rolePalette[0] ?? "chief-executive"
  );
}

/** Build just the agents + dependencies for a seed (mirrors the server), for reset/template use. */
export function buildSeedContent(
  catalog: Catalog,
  seed: ChildSeed,
): { agents: Agent[]; dependencies: Dependency[] } {
  if (seed.kind === "root") {
    return { agents: [agentFromRole(catalog, seed.roleKey)], dependencies: [] };
  }
  if (seed.kind === "formation") {
    return buildFormationSubtree(catalog, seed.formationKey, null, { x: 400, y: 100 });
  }
  return { agents: [], dependencies: [] };
}

export function newChildOrgDoc(
  catalog: Catalog,
  name: string,
  organizationType: string,
  seed: ChildSeed,
): OrganizationDoc {
  let agents: Agent[] = [];
  let dependencies: OrganizationDoc["dependencies"] = [];

  if (seed.kind === "root") {
    agents = [agentFromRole(catalog, seed.roleKey)];
  } else if (seed.kind === "formation") {
    const sub = buildFormationSubtree(catalog, seed.formationKey, null, { x: 400, y: 100 });
    agents = sub.agents;
    dependencies = sub.dependencies;
  }

  return {
    kind: "canopy.organization",
    schemaVersion: 1,
    id: crypto.randomUUID(),
    name,
    organizationType,
    agents,
    dependencies,
    customRoles: [],
    childOrganizations: [],
    meta: {},
  };
}
