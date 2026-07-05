// Dagre top→bottom layout of the current canvas's reporting tree (docs §7.4).
// Dependency edges are ignored for ranking; the result is applied as one undo unit.
import dagre from "@dagrejs/dagre";
import type { OrganizationDoc } from "../schema/organization";
import type { LayoutDirection } from "../store/settingsStore";

const NODE_W = 220;
const NODE_H = 84;

export function layoutReportingTree(
  org: OrganizationDoc,
  direction: LayoutDirection = "BT",
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: direction, nodesep: 40, ranksep: 90, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const a of org.agents) g.setNode(a.id, { width: NODE_W, height: NODE_H });
  for (const c of org.childOrganizations) {
    g.setNode(c.organization.id, { width: NODE_W, height: NODE_H });
  }

  for (const a of org.agents) {
    if (a.managerId && g.hasNode(a.managerId)) g.setEdge(a.managerId, a.id);
  }
  for (const c of org.childOrganizations) {
    if (g.hasNode(c.mountAgentId)) g.setEdge(c.mountAgentId, c.organization.id);
  }

  dagre.layout(g);

  const positions = new Map<string, { x: number; y: number }>();
  for (const id of g.nodes()) {
    const n = g.node(id);
    if (n) positions.set(id, { x: n.x - NODE_W / 2, y: n.y - NODE_H / 2 });
  }
  return positions;
}
