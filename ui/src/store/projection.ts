// Pure projection: derive React Flow nodes/edges for the currently open org (docs §7.5).
// Reporting edges come from managerId; dependency edges from the dependency list; child orgs
// render as single opaque nodes. React Flow never owns document data — this is the only bridge.
import type { Edge, Node } from "@xyflow/react";
import { MarkerType } from "@xyflow/react";
import type { Catalog, CatalogRole } from "../schema/catalog";
import type { Agent, ChildOrganizationDoc, CustomRole, OrganizationDoc } from "../schema/organization";
import type { LayoutDirection } from "./settingsStore";

export interface AgentNodeData extends Record<string, unknown> {
  agent: Agent;
  role: CatalogRole | CustomRole | undefined;
  isManager: boolean;
  selected: boolean;
  hasIssue: boolean;
  direction: LayoutDirection;
  status?: string; // live actuation status for this node (A2), undefined when not actuated
}

export interface ChildOrgNodeData extends Record<string, unknown> {
  child: ChildOrganizationDoc;
  typeTitle: string;
  section: string;
  agentCount: number;
  selected: boolean;
  hasIssue: boolean;
  direction: LayoutDirection;
}

export interface ProjectionInput {
  org: OrganizationDoc;
  catalog: Catalog;
  selectedId?: string;
  issueAgentIds: Set<string>;
  issueDepIds: Set<string>;
  direction: LayoutDirection;
  nodeStatus?: Map<string, string>; // nodeId -> live actuation status (A2)
}

function resolveRole(
  catalog: Catalog,
  org: OrganizationDoc,
  key: string,
): CatalogRole | CustomRole | undefined {
  return catalog.roles.find((r) => r.key === key) ?? org.customRoles.find((r) => r.key === key);
}

function recursiveAgentCount(org: OrganizationDoc): number {
  return org.agents.length + org.childOrganizations.reduce((n, c) => n + recursiveAgentCount(c.organization), 0);
}

export function projectNodes(input: ProjectionInput): Node[] {
  const { org, catalog, selectedId, issueAgentIds, issueDepIds, direction } = input;
  void issueDepIds;
  const nodes: Node[] = [];

  for (const agent of org.agents) {
    const role = resolveRole(catalog, org, agent.role.key);
    nodes.push({
      id: agent.id,
      type: "agent",
      position: agent.position,
      data: {
        agent,
        role,
        isManager: role?.isManager ?? false,
        selected: selectedId === agent.id,
        hasIssue: issueAgentIds.has(agent.id),
        direction,
        status: input.nodeStatus?.get(agent.id),
      } satisfies AgentNodeData,
      selected: selectedId === agent.id,
    });
  }

  for (const child of org.childOrganizations) {
    const type = catalog.organizationTypes.find((o) => o.key === child.organization.organizationType);
    nodes.push({
      id: child.organization.id,
      type: "childOrg",
      // child org nodes float near their mount agent unless positioned; use a stored meta if present
      position: (child.organization.meta?.position as { x: number; y: number }) ?? { x: 400, y: 460 },
      data: {
        child,
        typeTitle: type?.title ?? child.organization.organizationType,
        section: type?.section ?? "corporate-chassis",
        agentCount: recursiveAgentCount(child.organization),
        selected: selectedId === child.organization.id,
        hasIssue: issueAgentIds.has(child.organization.id),
        direction,
      } satisfies ChildOrgNodeData,
      selected: selectedId === child.organization.id,
    });
  }

  return nodes;
}

export function projectEdges(input: ProjectionInput): Edge[] {
  const { org, selectedId, issueDepIds } = input;
  const edges: Edge[] = [];

  // Reporting edges (solid) from managerId.
  for (const agent of org.agents) {
    if (agent.managerId) {
      edges.push({
        id: `report:${agent.id}`,
        source: agent.managerId,
        sourceHandle: "report-source",
        target: agent.id,
        targetHandle: "report-target",
        type: "reporting",
      });
    }
  }
  // A mounted child org reports to its mount agent.
  for (const child of org.childOrganizations) {
    edges.push({
      id: `report:${child.organization.id}`,
      source: child.mountAgentId,
      sourceHandle: "report-source",
      target: child.organization.id,
      targetHandle: "report-target",
      type: "reporting",
    });
  }

  // Dependency edges (dashed, arrow toward the dependency). from depends on to.
  for (const dep of org.dependencies) {
    edges.push({
      id: dep.id,
      source: dep.from,
      sourceHandle: "dep-left",
      target: dep.to,
      targetHandle: "dep-right",
      type: "dependency",
      selected: selectedId === dep.id,
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      data: { hasIssue: issueDepIds.has(dep.id), note: dep.note },
    });
  }

  return edges;
}
