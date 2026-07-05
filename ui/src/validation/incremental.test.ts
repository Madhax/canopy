import { describe, expect, it } from "vitest";
import type { OrganizationDoc } from "../schema/organization";
import { checkDependency, checkReparent } from "./incremental";

function doc(): OrganizationDoc {
  const agent = (id: string, managerId: string | null) => ({
    id,
    name: id,
    role: { key: "backend-engineer", version: 1 },
    managerId,
    extensions: { instructions: "", responsibilities: [] },
    salary: { perAssignmentAllowance: 150000, warnThresholdPct: 80, hardStop: true },
    position: { x: 0, y: 0 },
  });
  return {
    kind: "canopy.organization",
    schemaVersion: 1,
    id: "o1",
    name: "T",
    organizationType: "product-engineering",
    agents: [
      agent("root", null),
      agent("l1", "root"),
      agent("l2", "root"),
      agent("c1", "l1"),
      agent("c2", "l1"),
      agent("x", "l2"),
    ],
    dependencies: [{ id: "d1", from: "c1", to: "c2", note: null }],
    customRoles: [],
    childOrganizations: [],
    meta: {},
  };
}

describe("checkReparent", () => {
  it("rejects a self-parent", () => {
    expect(checkReparent(doc(), "l1", "l1").ok).toBe(false);
  });
  it("rejects a cycle (parenting a manager under its own descendant)", () => {
    expect(checkReparent(doc(), "root", "c1").code).toBe("REPORTS_CYCLE");
  });
  it("allows a valid re-parent", () => {
    expect(checkReparent(doc(), "x", "l1").ok).toBe(true);
  });
});

describe("checkDependency", () => {
  it("rejects self-dependency", () => {
    expect(checkDependency(doc(), "c1", "c1").code).toBe("DEP_SELF");
  });
  it("rejects cross-team dependencies (siblings only)", () => {
    expect(checkDependency(doc(), "c1", "x").code).toBe("DEP_NOT_SIBLINGS");
  });
  it("rejects duplicate dependencies", () => {
    expect(checkDependency(doc(), "c1", "c2").code).toBe("DEP_DUPLICATE");
  });
  it("rejects a dependency cycle", () => {
    // c1->c2 exists; adding c2->c1 would close a cycle
    expect(checkDependency(doc(), "c2", "c1").code).toBe("DEP_CYCLE");
  });
  it("allows a valid sibling dependency", () => {
    // l1 and l2 are siblings under root; no existing edge between them
    expect(checkDependency(doc(), "l1", "l2").ok).toBe(true);
  });
});
