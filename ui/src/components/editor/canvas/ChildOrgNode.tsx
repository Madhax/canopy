import { Handle, Position, type NodeProps } from "@xyflow/react";
import { memo } from "react";
import type { ChildOrgNodeData } from "../../../store/projection";
import { sectionColor } from "../../../lib/theme";

function ChildOrgNodeImpl({ data, selected }: NodeProps & { data: ChildOrgNodeData }) {
  const { child, typeTitle, section, agentCount, hasIssue, direction } = data;
  const color = sectionColor(section);
  // A child org only reports upward; its incoming handle sits toward its manager.
  const targetPos = direction === "BT" ? Position.Bottom : Position.Top;

  return (
    <div
      className={`relative w-[220px] rounded-node border-2 bg-surface-2 shadow-sm ${
        selected ? "border-accent ring-1 ring-accent" : "border-border-strong"
      }`}
    >
      {/* a child org reports to its mount agent and can be a sibling dependency endpoint */}
      <Handle type="target" position={targetPos} id="report-target" />
      <Handle type="source" position={Position.Left} id="dep-left" />
      <Handle type="target" position={Position.Right} id="dep-right" />

      <div className="px-3 py-2.5">
        <div className="flex items-center justify-between gap-1.5">
          <span
            className="truncate rounded px-1.5 py-0.5 text-[10px] font-medium"
            style={{ background: `${color}20`, color }}
          >
            {typeTitle}
          </span>
          {hasIssue && <span className="size-2 shrink-0 rounded-full bg-warn" />}
        </div>
        <div className="mt-1 truncate text-sm font-semibold text-ink">{child.organization.name}</div>
        <div className="mt-1 flex items-center justify-between text-[10px] text-ink-muted">
          <span>
            {agentCount} agent{agentCount === 1 ? "" : "s"}
          </span>
          <span className="font-medium text-accent">Open ⤢</span>
        </div>
      </div>
    </div>
  );
}

export const ChildOrgNode = memo(ChildOrgNodeImpl);
