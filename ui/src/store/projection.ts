// Pure projection: derive React Flow nodes/edges for the currently open team (docs §7.5).
// Reporting edges come from managerId; dependency edges from the dependency list; child teams
// render as single opaque nodes. React Flow never owns document data — this is the only bridge.
import type { Edge, Node } from "@xyflow/react";
import { MarkerType } from "@xyflow/react";
import type { Catalog, CatalogRole } from "../schema/catalog";
import type { Agent, ChildTeamDoc, CustomRole, TeamDoc } from "../schema/team";
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
  child: ChildTeamDoc;
  typeTitle: string;
  section: string;
  agentCount: number;
  selected: boolean;
  hasIssue: boolean;
  direction: LayoutDirection;
}

export interface ProjectionInput {
  team: TeamDoc;
  catalog: Catalog;
  selectedId?: string;
  issueAgentIds: Set<string>;
  issueDepIds: Set<string>;
  direction: LayoutDirection;
  nodeStatus?: Map<string, string>; // nodeId -> live actuation status (A2)
}

function resolveRole(
  catalog: Catalog,
  team: TeamDoc,
  key: string,
): CatalogRole | CustomRole | undefined {
  return catalog.roles.find((r) => r.key === key) ?? team.customRoles.find((r) => r.key === key);
}

function recursiveAgentCount(team: TeamDoc): number {
  return team.agents.length + team.childTeams.reduce((n, c) => n + recursiveAgentCount(c.team), 0);
}

export function projectNodes(input: ProjectionInput): Node[] {
  const { team, catalog, selectedId, issueAgentIds, issueDepIds, direction } = input;
  void issueDepIds;
  const nodes: Node[] = [];

  for (const agent of team.agents) {
    const role = resolveRole(catalog, team, agent.role.key);
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

  for (const child of team.childTeams) {
    const type = catalog.organizationTypes.find((o) => o.key === child.team.organizationType);
    nodes.push({
      id: child.team.id,
      type: "childTeam",
      // child team nodes float near their mount agent unless positioned; use a stored meta if present
      position: (child.team.meta?.position as { x: number; y: number }) ?? { x: 400, y: 460 },
      data: {
        child,
        typeTitle: type?.title ?? child.team.organizationType,
        section: type?.section ?? "corporate-chassis",
        agentCount: recursiveAgentCount(child.team),
        selected: selectedId === child.team.id,
        hasIssue: issueAgentIds.has(child.team.id),
        direction,
      } satisfies ChildOrgNodeData,
      selected: selectedId === child.team.id,
    });
  }

  return nodes;
}

export function projectEdges(input: ProjectionInput): Edge[] {
  const { team, selectedId, issueDepIds } = input;
  const edges: Edge[] = [];

  // Reporting edges (solid) from managerId.
  for (const agent of team.agents) {
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
  // A mounted child team reports to its mount agent.
  for (const child of team.childTeams) {
    edges.push({
      id: `report:${child.team.id}`,
      source: child.mountAgentId,
      sourceHandle: "report-source",
      target: child.team.id,
      targetHandle: "report-target",
      type: "reporting",
    });
  }

  // Dependency edges (dashed, arrow toward the dependency). from depends on to.
  for (const dep of team.dependencies) {
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
