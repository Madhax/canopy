// The connector overlay projection (builder-connectors.md §7), pinned as pure functions —
// the canvas edge layer can't render under the headless preview, so scope-as-edges is
// proven here: org-wide → one labeled edge to the root; node links → one edge per node;
// disabled/unlinked → nothing.
import { describe, expect, it } from "vitest";
import type { ConnectorInstance } from "../../../api/connectors";
import type { OrganizationDoc } from "../../../schema/organization";
import { connectorEdges, connectorNodes } from "./OrgCanvas";

const org = {
  agents: [
    { id: "a_root", managerId: null, position: { x: 400, y: 100 } },
    { id: "a_kid", managerId: "a_root", position: { x: 200, y: 260 } },
  ],
} as unknown as OrganizationDoc;

function inst(overrides: Partial<ConnectorInstance>): ConnectorInstance {
  return {
    id: "ci_1", organizationId: "o1", packKey: "github", name: "canopy repo",
    config: {}, secretBindings: {}, enabledGrants: [], nodeLinks: null, enabled: true,
    createdAt: "", updatedAt: "", ...overrides,
  };
}

describe("connector overlay projection", () => {
  it("org-wide links draw one labeled dashed edge to the root", () => {
    const edges = connectorEdges([inst({})], org);
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({
      source: "ci_1", target: "a_root", label: "org-wide",
      targetHandle: "report-target", sourceHandle: "connector-link",
    });
    expect(edges[0].style?.strokeDasharray).toBeTruthy();
  });

  it("node links draw one unlabeled edge per linked node, skipping ghosts", () => {
    const edges = connectorEdges([inst({ nodeLinks: ["a_kid", "a_ghost"] })], org);
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({ source: "ci_1", target: "a_kid", label: undefined });
  });

  it("disabled and unlinked instances draw nothing", () => {
    expect(connectorEdges([inst({ enabled: false })], org)).toHaveLength(0);
    expect(connectorEdges([inst({ nodeLinks: [] })], org)).toHaveLength(0);
  });

  it("pills park left of the chart and carry state chips in data", () => {
    const nodes = connectorNodes(
      [inst({}), inst({ id: "ci_2", nodeLinks: [] })], org, new Set(["ci_1"]), "ci_1",
    );
    expect(nodes).toHaveLength(2);
    expect(nodes[0].position.x).toBeLessThan(200); // left of the chart's min x
    expect(nodes[0].data).toMatchObject({ orgWide: true, governed: true, selected: true });
    expect(nodes[1].data).toMatchObject({ unlinked: true, governed: false, selected: false });
  });
});
