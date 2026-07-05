import { Handle, Position, type NodeProps } from "@xyflow/react";
import { memo } from "react";
import type { AgentNodeData } from "../../../store/projection";
import { roleGroupColor } from "../../../lib/theme";
import { formatSalary } from "../../../lib/format";

function AgentNodeImpl({ data, selected }: NodeProps & { data: AgentNodeData }) {
  const { agent, role, isManager, hasIssue, direction } = data;
  const color = roleGroupColor(role?.group ?? "custom");
  const roleTitle = role?.title ?? agent.role.key;
  // Bottom-up (BT): the manager sits below its reports, so its outgoing handle is on top.
  const sourcePos = direction === "BT" ? Position.Top : Position.Bottom;
  const targetPos = direction === "BT" ? Position.Bottom : Position.Top;

  return (
    <div
      className={`relative w-[220px] rounded-node border bg-surface shadow-sm transition-shadow ${
        selected ? "border-accent shadow-md ring-1 ring-accent" : "border-border"
      }`}
      style={{ borderLeft: `4px solid ${color}` }}
    >
      {/* reporting handles — placed per layout direction (docs: bottom-up default) */}
      <Handle type="target" position={targetPos} id="report-target" />
      <Handle type="source" position={sourcePos} id="report-source" />
      {/* dependency handles (left source = dependent, right target = dependency) */}
      <Handle type="source" position={Position.Left} id="dep-left" />
      <Handle type="target" position={Position.Right} id="dep-right" />

      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-[10px] font-medium uppercase tracking-wide" style={{ color }}>
            {roleTitle}
          </span>
          {isManager && (
            <span className="text-[10px]" style={{ color }} title="Manager role" aria-hidden>
              ♛
            </span>
          )}
          {hasIssue && (
            <span
              className="ml-auto size-2 shrink-0 rounded-full bg-warn"
              title="This node is implicated in a validation issue"
            />
          )}
        </div>
        <div className="truncate text-sm font-semibold text-ink">{agent.name}</div>
        {selected && (
          <div className="mt-1 text-[10px] text-ink-muted">{formatSalary(agent.salary)}</div>
        )}
      </div>
    </div>
  );
}

export const AgentNode = memo(AgentNodeImpl);
