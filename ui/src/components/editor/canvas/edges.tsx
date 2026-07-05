import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";

export function ReportingEdge(props: EdgeProps) {
  const [path] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  });
  return (
    <BaseEdge
      id={props.id}
      path={path}
      style={{ stroke: "var(--color-border-strong)", strokeWidth: 1.5 }}
    />
  );
}

export function DependencyEdge(props: EdgeProps) {
  const [path] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  });
  const hasIssue = (props.data as { hasIssue?: boolean } | undefined)?.hasIssue;
  return (
    <BaseEdge
      id={props.id}
      path={path}
      markerEnd={props.markerEnd}
      style={{
        stroke: hasIssue ? "var(--color-warn)" : props.selected ? "var(--color-accent)" : "#9a8",
        strokeWidth: props.selected ? 2 : 1.5,
        strokeDasharray: "5 4",
      }}
    />
  );
}
