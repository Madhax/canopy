import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  useUpdateNodeInternals,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import type { Catalog } from "../../../schema/catalog";
import type { TeamDoc } from "../../../schema/team";
import { checkDependency, checkReparent } from "../../../validation/incremental";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { useSettingsStore } from "../../../store/settingsStore";
import { projectEdges, projectNodes } from "../../../store/projection";
import { useToast } from "../../common";
import type { ConnectorInstance } from "../../../api/connectors";
import { AgentNode } from "./AgentNode";
import { ChildOrgNode } from "./ChildOrgNode";
import { ConnectorPill } from "./ConnectorPill";
import { DependencyEdge, ReportingEdge } from "./edges";

const nodeTypes = { agent: AgentNode, childTeam: ChildOrgNode, connector: ConnectorPill };
const edgeTypes = { reporting: ReportingEdge, dependency: DependencyEdge };

interface Props {
  team: TeamDoc;
  catalog: Catalog;
  issueAgentIds: Set<string>;
  issueDepIds: Set<string>;
  onOpenChild: (childTeamId: string) => void;
  nodeStatus?: Map<string, string>;
  // Connector overlay (builder-connectors.md §7): instances are server truth projected onto
  // the canvas as pills + dashed scope edges — never chart data, never in undo history.
  connectors?: ConnectorInstance[];
  connectorGoverned?: Set<string>; // instance ids whose enabled grants carry governed actions
  selectedConnectorId?: string | null;
  onSelectConnector?: (id: string | null) => void;
  onLinkConnector?: (instanceId: string, targetNodeId: string) => void;
  onDropConnector?: (packKey: string, position: { x: number; y: number }) => void;
}

// Pills park in a column left of the chart; positions are presentation, not document state.
// Exported for tests: the canvas edge layer can't render in the headless preview (rAF),
// so the projection is pinned as pure functions.
export function connectorNodes(
  connectors: ConnectorInstance[], team: TeamDoc, governed: Set<string>,
  selectedId: string | null | undefined,
): Node[] {
  const minX = team.agents.length ? Math.min(...team.agents.map((a) => a.position.x)) : 360;
  const minY = team.agents.length ? Math.min(...team.agents.map((a) => a.position.y)) : 120;
  return connectors.map((c, i) => ({
    id: c.id,
    type: "connector" as const,
    position: { x: minX - 300, y: minY + i * 72 },
    draggable: false,
    data: {
      name: c.name, packKey: c.packKey, packTitle: c.packKey, enabled: c.enabled,
      unlinked: c.nodeLinks !== null && c.nodeLinks.length === 0,
      orgWide: c.nodeLinks === null, governed: governed.has(c.id),
      selected: selectedId === c.id,
    },
  }));
}

export function connectorEdges(connectors: ConnectorInstance[], team: TeamDoc): Edge[] {
  const root = team.agents.find((a) => a.managerId === null);
  const out: Edge[] = [];
  for (const c of connectors) {
    if (!c.enabled) continue;
    const targets = c.nodeLinks === null ? (root ? [root.id] : []) : c.nodeLinks;
    for (const t of targets) {
      if (!team.agents.some((a) => a.id === t)) continue;
      out.push({
        id: `cl-${c.id}-${t}`,
        source: c.id,
        sourceHandle: "connector-link",
        target: t,
        targetHandle: "report-target",
        type: "default",
        style: { strokeDasharray: "6 3", stroke: "var(--color-border-strong, #888)" },
        label: c.nodeLinks === null ? "team-wide" : undefined,
        labelStyle: { fontSize: 9, fill: "var(--color-ink-muted)" },
        selectable: false,
      });
    }
  }
  return out;
}

function Canvas({
  team, catalog, issueAgentIds, issueDepIds, onOpenChild, nodeStatus,
  connectors, connectorGoverned, selectedConnectorId, onSelectConnector, onLinkConnector,
  onDropConnector,
}: Props) {
  const { toast } = useToast();
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);
  const selection = useSelectionStore((s) => s.selection);
  const select = useSelectionStore((s) => s.select);
  const { screenToFlowPosition } = useReactFlow();
  const updateNodeInternals = useUpdateNodeInternals();
  const direction = useSettingsStore((s) => s.layoutDirection);
  const dragging = useRef(false);

  const selectedId = selection.kind !== "none" ? selection.id : undefined;
  const projectionInput = useMemo(
    () => ({ team, catalog, selectedId, issueAgentIds, issueDepIds, direction, nodeStatus }),
    [team, catalog, selectedId, issueAgentIds, issueDepIds, direction, nodeStatus],
  );

  const overlay = useMemo(() => {
    const list = connectors ?? [];
    const governed = connectorGoverned ?? new Set<string>();
    return {
      nodes: connectorNodes(list, team, governed, selectedConnectorId),
      edges: connectorEdges(list, team),
    };
  }, [connectors, connectorGoverned, selectedConnectorId, team]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(
    [...projectNodes(projectionInput), ...overlay.nodes],
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(
    [...projectEdges(projectionInput), ...overlay.edges],
  );

  // Re-project when the document / selection / issues / overlay change — but never mid-drag.
  useEffect(() => {
    if (dragging.current) return;
    setNodes([...projectNodes(projectionInput), ...overlay.nodes]);
    setEdges([...projectEdges(projectionInput), ...overlay.edges]);
  }, [projectionInput, overlay, setNodes, setEdges]);

  // Reporting handles sit on the top or bottom edge depending on layout direction. React Flow
  // caches handle positions when a node mounts, so on first paint (and whenever the direction
  // flips) the reporting edges can anchor to stale positions until we ask it to re-measure.
  // Defer the re-measure across two animation frames so it runs AFTER the handles have painted
  // at their new positions — otherwise the very first render routes edges to the wrong edge.
  const nodeIdsKey =
    team.agents.map((a) => a.id).join(",") +
    "#" +
    team.childTeams.map((c) => c.team.id).join(",");
  useEffect(() => {
    const ids = [
      ...team.agents.map((a) => a.id),
      ...team.childTeams.map((c) => c.team.id),
    ];
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => ids.forEach(updateNodeInternals));
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [direction, nodeIdsKey, updateNodeInternals]);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      if (changes.some((c) => c.type === "position" && c.dragging)) dragging.current = true;
      onNodesChange(changes);
    },
    [onNodesChange],
  );

  const onNodeDragStop = useCallback(
    (_: unknown, node: Node) => {
      dragging.current = false;
      if (node.type === "agent") store.moveAgent(path, node.id, node.position);
    },
    [store, path],
  );

  // Handle pairing determines meaning — no edge-mode toggle (docs §7.4). The connector-link
  // pair is the scope gesture (builder-connectors-ux.md §2.2).
  const isValidConnection = useCallback((c: Connection | Edge) => {
    if (c.source === c.target) return false;
    const reporting = c.sourceHandle === "report-source" && c.targetHandle === "report-target";
    const dependency = c.sourceHandle === "dep-left" && c.targetHandle === "dep-right";
    const link = c.sourceHandle === "connector-link" && c.targetHandle === "report-target";
    return reporting || dependency || link;
  }, []);

  const onConnect = useCallback(
    (c: Connection) => {
      if (!c.source || !c.target) return;
      if (c.sourceHandle === "connector-link") {
        // connector scope: link the instance to the target node (the root = team-wide).
        if (team.agents.some((a) => a.id === c.target)) onLinkConnector?.(c.source, c.target);
        return;
      }
      if (c.sourceHandle === "report-source" && c.targetHandle === "report-target") {
        // reporting: the target reports to the source (re-parent)
        const res = checkReparent(team, c.target, c.source);
        if (!res.ok) return toast(res.message ?? "Invalid connection.", "error");
        store.reparentAgent(path, c.target, c.source);
      } else if (c.sourceHandle === "dep-left" && c.targetHandle === "dep-right") {
        // dependency: source depends on target
        const res = checkDependency(team, c.source, c.target);
        if (!res.ok) return toast(res.message ?? "Invalid connection.", "error");
        store.addDependency(path, c.source, c.target);
      }
    },
    [team, path, store, toast, onLinkConnector],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });

      const roleKey = event.dataTransfer.getData("application/canopy-role");
      if (roleKey) {
        const id = store.placeAgent(path, roleKey, position, catalog);
        select({ kind: "agent", id });
        return;
      }

      const packKey = event.dataTransfer.getData("application/canopy-connector");
      if (packKey) {
        onDropConnector?.(packKey, position);
        return;
      }

      const formationKey = event.dataTransfer.getData("application/canopy-formation");
      if (formationKey) {
        // Drop-on-agent: the formation manager reports to that agent. Otherwise, on a rootless
        // chart the manager becomes the root; on a rooted chart it attaches under the root.
        const nodeEl = (event.target as HTMLElement).closest(".react-flow__node");
        const droppedOnId = nodeEl?.getAttribute("data-id") ?? null;
        const onAgent = team.agents.find((a) => a.id === droppedOnId);
        const root = team.agents.find((a) => a.managerId === null);
        const mount = onAgent ? onAgent.id : root ? root.id : null;
        store.stampFormation(path, formationKey, mount, position, catalog);
      }
    },
    [screenToFlowPosition, store, path, catalog, select, team],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }, []);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.type === "connector") {
        onSelectConnector?.(node.id);
        select({ kind: "none" });
        return;
      }
      onSelectConnector?.(null);
      if (node.type === "childTeam") select({ kind: "childTeam", id: node.id });
      else select({ kind: "agent", id: node.id });
    },
    [select, onSelectConnector],
  );

  const onNodeDoubleClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.type === "childTeam") onOpenChild(node.id);
    },
    [onOpenChild],
  );

  const onEdgeClick = useCallback(
    (_: unknown, edge: Edge) => {
      if (edge.type === "dependency") select({ kind: "dependency", id: edge.id });
    },
    [select],
  );

  const onPaneClick = useCallback(() => {
    onSelectConnector?.(null);
    select({ kind: "none" });
  }, [select, onSelectConnector]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={handleNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeDragStop={onNodeDragStop}
      onConnect={onConnect}
      isValidConnection={isValidConnection}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onNodeClick={onNodeClick}
      onNodeDoubleClick={onNodeDoubleClick}
      onEdgeClick={onEdgeClick}
      onPaneClick={onPaneClick}
      deleteKeyCode={null}
      fitView
      fitViewOptions={{ padding: 0.3, maxZoom: 1 }}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--color-border)" />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable className="!bg-surface-2" />
    </ReactFlow>
  );
}

export function OrgCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}
