import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import type { Catalog } from "../schema/catalog";
import type { OrganizationDoc } from "../schema/organization";
import { useDocumentStore, useTemporalStore } from "./documentStore";

const here = dirname(fileURLToPath(import.meta.url));
const catalog = JSON.parse(
  readFileSync(join(here, "..", "..", "..", "catalog", "catalog.json"), "utf-8"),
) as Catalog;

function freshDoc(): OrganizationDoc {
  return {
    kind: "canopy.organization",
    schemaVersion: 1,
    id: "o1",
    name: "Test",
    organizationType: "product-engineering",
    agents: [],
    dependencies: [],
    customRoles: [],
    childOrganizations: [],
    meta: {},
  };
}

const store = () => useDocumentStore.getState();
const doc = () => useDocumentStore.getState().doc!;

beforeEach(() => {
  store().load(freshDoc());
  useTemporalStore.getState().clear();
});

describe("documentStore", () => {
  it("places an agent from a role with the role default salary", () => {
    const id = store().placeAgent([], "engineering-lead", { x: 0, y: 0 }, catalog);
    const agent = doc().agents.find((a) => a.id === id)!;
    expect(agent.role.key).toBe("engineering-lead");
    expect(agent.salary.perAssignmentAllowance).toBe(160000);
    expect(agent.managerId).toBeNull();
  });

  it("reparents an agent by setting managerId", () => {
    const lead = store().placeAgent([], "engineering-lead", { x: 0, y: 0 }, catalog);
    const be = store().placeAgent([], "backend-engineer", { x: 0, y: 100 }, catalog);
    store().reparentAgent([], be, lead);
    expect(doc().agents.find((a) => a.id === be)!.managerId).toBe(lead);
  });

  it("deleting a manager orphans its reports and drops its dependencies", () => {
    const lead = store().placeAgent([], "engineering-lead", { x: 0, y: 0 }, catalog);
    const be = store().placeAgent([], "backend-engineer", { x: 0, y: 100 }, catalog);
    const qa = store().placeAgent([], "qa-engineer", { x: 100, y: 100 }, catalog);
    store().reparentAgent([], be, lead);
    store().reparentAgent([], qa, lead);
    store().addDependency([], qa, be);
    store().deleteAgent([], lead);
    expect(doc().agents.find((a) => a.id === be)!.managerId).toBeNull();
    expect(doc().dependencies.length).toBe(1); // qa->be survives; none referenced lead
    store().deleteAgent([], be);
    expect(doc().dependencies.length).toBe(0); // qa->be removed with be
  });

  it("stamps a formation as a single undo unit", () => {
    store().stampFormation([], "product-engineering-pod", null, { x: 400, y: 100 }, catalog);
    expect(doc().agents.length).toBe(4);
    expect(doc().dependencies.length).toBe(2);
    // one history entry -> a single undo reverts the whole stamp
    useTemporalStore.getState().undo();
    expect(doc().agents.length).toBe(0);
    useTemporalStore.getState().redo();
    expect(doc().agents.length).toBe(4);
  });

  it("mounts a child organization under an agent", () => {
    const lead = store().placeAgent([], "engineering-lead", { x: 0, y: 0 }, catalog);
    store().mountChildOrg([], lead, {
      kind: "canopy.organization",
      schemaVersion: 1,
      id: "child1",
      name: "Support",
      organizationType: "customer-support-center",
      agents: [],
      dependencies: [],
      customRoles: [],
      childOrganizations: [],
      meta: {},
    });
    expect(doc().childOrganizations.length).toBe(1);
    expect(doc().childOrganizations[0].mountAgentId).toBe(lead);
    expect(doc().childOrganizations[0].organization.name).toBe("Support");
  });

  it("adds a document-local custom role (upserting by key)", () => {
    const role = {
      key: "custom-release-captain",
      version: 1,
      title: "Release Captain",
      group: "custom",
      purpose: "Owns releases.",
      responsibilities: [{ duty: "Cut releases", deliverable: { kind: "artifact" as const, type: "ReleaseCandidate" } }],
      isManager: false,
      defaultSalary: { perAssignmentAllowance: 120000, warnThresholdPct: 80, hardStop: true },
    };
    store().addCustomRole([], role);
    store().addCustomRole([], { ...role, title: "Release Captain v2" });
    expect(doc().customRoles.length).toBe(1); // upsert, not duplicate
    expect(doc().customRoles[0].title).toBe("Release Captain v2");
  });

  it("replaceChart swaps agents/deps and drops child orgs as one undo unit", () => {
    store().stampFormation([], "product-engineering-pod", null, { x: 0, y: 0 }, catalog);
    const lead = doc().agents.find((a) => a.managerId === null)!.id;
    store().mountChildOrg([], lead, {
      kind: "canopy.organization",
      schemaVersion: 1,
      id: "c1",
      name: "C",
      organizationType: "customer-support-center",
      agents: [],
      dependencies: [],
      customRoles: [],
      childOrganizations: [],
      meta: {},
    });
    expect(doc().childOrganizations.length).toBe(1);

    store().replaceChart([], [], []);
    expect(doc().agents.length).toBe(0);
    expect(doc().dependencies.length).toBe(0);
    expect(doc().childOrganizations.length).toBe(0);

    // undoable
    useTemporalStore.getState().undo();
    expect(doc().agents.length).toBe(4);
    expect(doc().childOrganizations.length).toBe(1);
  });

  it("undo/redo steps through named actions", () => {
    store().placeAgent([], "engineering-lead", { x: 0, y: 0 }, catalog);
    store().placeAgent([], "backend-engineer", { x: 0, y: 100 }, catalog);
    expect(doc().agents.length).toBe(2);
    useTemporalStore.getState().undo();
    expect(doc().agents.length).toBe(1);
    useTemporalStore.getState().undo();
    expect(doc().agents.length).toBe(0);
  });
});
