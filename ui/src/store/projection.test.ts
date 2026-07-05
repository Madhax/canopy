import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import type { Catalog } from "../schema/catalog";
import type { OrganizationDoc } from "../schema/organization";
import { projectEdges, projectNodes } from "./projection";

const here = dirname(fileURLToPath(import.meta.url));
const catalog = JSON.parse(
  readFileSync(join(here, "..", "..", "..", "catalog", "catalog.json"), "utf-8"),
) as Catalog;

function pod(): OrganizationDoc {
  return {
    kind: "canopy.organization",
    schemaVersion: 1,
    id: "o1",
    name: "Pod",
    organizationType: "product-engineering",
    agents: [
      { id: "a_lead", name: "Lead", role: { key: "engineering-lead", version: 1 }, managerId: null, extensions: { instructions: "", responsibilities: [] }, salary: { perAssignmentAllowance: 160000, warnThresholdPct: 80, hardStop: true }, position: { x: 0, y: 0 } },
      { id: "a_be", name: "BE", role: { key: "backend-engineer", version: 1 }, managerId: "a_lead", extensions: { instructions: "", responsibilities: [] }, salary: { perAssignmentAllowance: 150000, warnThresholdPct: 80, hardStop: true }, position: { x: 0, y: 100 } },
    ],
    dependencies: [{ id: "d1", from: "a_be", to: "a_lead", note: null }],
    customRoles: [],
    childOrganizations: [],
    meta: {},
  };
}

const input = () => ({
  org: pod(),
  catalog,
  issueAgentIds: new Set<string>(),
  issueDepIds: new Set<string>(),
  direction: "BT" as const,
});

describe("projection", () => {
  it("projects agents to agent nodes", () => {
    const nodes = projectNodes(input());
    expect(nodes.map((n) => n.id).sort()).toEqual(["a_be", "a_lead"]);
    expect(nodes.every((n) => n.type === "agent")).toBe(true);
  });

  it("derives a reporting edge from managerId", () => {
    const edges = projectEdges(input());
    const reporting = edges.find((e) => e.type === "reporting")!;
    expect(reporting.source).toBe("a_lead"); // manager is the source
    expect(reporting.target).toBe("a_be");
  });

  it("derives a dependency edge from the dependency list", () => {
    const edges = projectEdges(input());
    const dep = edges.find((e) => e.type === "dependency")!;
    expect(dep.id).toBe("d1");
    expect(dep.source).toBe("a_be"); // the dependent
    expect(dep.target).toBe("a_lead"); // the dependency
  });

  it("marks the manager role via node data", () => {
    const nodes = projectNodes(input());
    const lead = nodes.find((n) => n.id === "a_lead")!;
    expect((lead.data as { isManager: boolean }).isManager).toBe(true);
  });
});
