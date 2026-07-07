import { Handle, Position, type NodeProps } from "@xyflow/react";
import { memo } from "react";
import type { AgentNodeData } from "../../../store/projection";
import { roleGroupColor } from "../../../lib/theme";
import { formatSalary } from "../../../lib/format";

const STATUS_TONE: Record<string, string> = {
  ready: "bg-ok/15 text-ok",
  idle: "bg-ok/15 text-ok",
  engaged: "bg-accent/15 text-accent",
  booting: "bg-warn/15 text-warn",
  provisioning: "bg-warn/15 text-warn",
  pending: "bg-warn/15 text-warn",
  paused: "bg-warn/15 text-warn",
  failed: "bg-danger/15 text-danger",
  dead: "bg-danger/15 text-danger",
};

function AgentNodeImpl({ data, selected }: NodeProps & { data: AgentNodeData }) {
  const { agent, role, isManager, hasIssue, direction, status } = data;
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
        {status && (
          <div className="mt-1">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide ${
                STATUS_TONE[status] ?? "bg-surface-2 text-ink-muted"
              }`}
            >
              <span className="size-1.5 rounded-full bg-current" />
              {status}
            </span>
          </div>
        )}
        {selected && (
          <div className="mt-1 text-[10px] text-ink-muted">{formatSalary(agent.salary)}</div>
        )}
      </div>
    </div>
  );
}

export const AgentNode = memo(AgentNodeImpl);
