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
import type { OrganizationDoc } from "../../../schema/organization";
import { checkDependency, checkReparent } from "../../../validation/incremental";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { useSettingsStore } from "../../../store/settingsStore";
import { projectEdges, projectNodes } from "../../../store/projection";
import { useToast } from "../../common";
import { AgentNode } from "./AgentNode";
import { ChildOrgNode } from "./ChildOrgNode";
import { DependencyEdge, ReportingEdge } from "./edges";

const nodeTypes = { agent: AgentNode, childOrg: ChildOrgNode };
const edgeTypes = { reporting: ReportingEdge, dependency: DependencyEdge };

interface Props {
  org: OrganizationDoc;
  catalog: Catalog;
  issueAgentIds: Set<string>;
  issueDepIds: Set<string>;
  onOpenChild: (childOrgId: string) => void;
}

function Canvas({ org, catalog, issueAgentIds, issueDepIds, onOpenChild }: Props) {
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
    () => ({ org, catalog, selectedId, issueAgentIds, issueDepIds, direction }),
    [org, catalog, selectedId, issueAgentIds, issueDepIds, direction],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(projectNodes(projectionInput));
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(projectEdges(projectionInput));

  // Re-project when the document / selection / issues change — but never mid-drag.
  useEffect(() => {
    if (dragging.current) return;
    setNodes(projectNodes(projectionInput));
    setEdges(projectEdges(projectionInput));
  }, [projectionInput, setNodes, setEdges]);

  // Reporting handles sit on the top or bottom edge depending on layout direction. React Flow
  // caches handle positions when a node mounts, so on first paint (and whenever the direction
  // flips) the reporting edges can anchor to stale positions until we ask it to re-measure.
  // Defer the re-measure across two animation frames so it runs AFTER the handles have painted
  // at their new positions — otherwise the very first render routes edges to the wrong edge.
  const nodeIdsKey =
    org.agents.map((a) => a.id).join(",") +
    "#" +
    org.childOrganizations.map((c) => c.organization.id).join(",");
  useEffect(() => {
    const ids = [
      ...org.agents.map((a) => a.id),
      ...org.childOrganizations.map((c) => c.organization.id),
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

  // Handle pairing determines meaning — no edge-mode toggle (docs §7.4).
  const isValidConnection = useCallback((c: Connection | Edge) => {
    if (c.source === c.target) return false;
    const reporting = c.sourceHandle === "report-source" && c.targetHandle === "report-target";
    const dependency = c.sourceHandle === "dep-left" && c.targetHandle === "dep-right";
    return reporting || dependency;
  }, []);

  const onConnect = useCallback(
    (c: Connection) => {
      if (!c.source || !c.target) return;
      if (c.sourceHandle === "report-source" && c.targetHandle === "report-target") {
        // reporting: the target reports to the source (re-parent)
        const res = checkReparent(org, c.target, c.source);
        if (!res.ok) return toast(res.message ?? "Invalid connection.", "error");
        store.reparentAgent(path, c.target, c.source);
      } else if (c.sourceHandle === "dep-left" && c.targetHandle === "dep-right") {
        // dependency: source depends on target
        const res = checkDependency(org, c.source, c.target);
        if (!res.ok) return toast(res.message ?? "Invalid connection.", "error");
        store.addDependency(path, c.source, c.target);
      }
    },
    [org, path, store, toast],
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

      const formationKey = event.dataTransfer.getData("application/canopy-formation");
      if (formationKey) {
        // Drop-on-agent: the formation manager reports to that agent. Otherwise, on a rootless
        // chart the manager becomes the root; on a rooted chart it attaches under the root.
        const nodeEl = (event.target as HTMLElement).closest(".react-flow__node");
        const droppedOnId = nodeEl?.getAttribute("data-id") ?? null;
        const onAgent = org.agents.find((a) => a.id === droppedOnId);
        const root = org.agents.find((a) => a.managerId === null);
        const mount = onAgent ? onAgent.id : root ? root.id : null;
        store.stampFormation(path, formationKey, mount, position, catalog);
      }
    },
    [screenToFlowPosition, store, path, catalog, select, org],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }, []);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.type === "childOrg") select({ kind: "childOrg", id: node.id });
      else select({ kind: "agent", id: node.id });
    },
    [select],
  );

  const onNodeDoubleClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.type === "childOrg") onOpenChild(node.id);
    },
    [onOpenChild],
  );

  const onEdgeClick = useCallback(
    (_: unknown, edge: Edge) => {
      if (edge.type === "dependency") select({ kind: "dependency", id: edge.id });
    },
    [select],
  );

  const onPaneClick = useCallback(() => select({ kind: "none" }), [select]);

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
