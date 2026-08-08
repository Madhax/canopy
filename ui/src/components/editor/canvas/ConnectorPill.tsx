// The connector instance on the canvas (builder-connectors-ux.md §2.2): visually NOT an
// agent — square-cornered, icon-led — with one source handle for the link gesture. Scope is
// the edge; an unlinked instance renders dimmed with an "unlinked" chip.
import { Handle, Position, type NodeProps } from "@xyflow/react";

const PACK_ICONS: Record<string, string> = { github: "◆", "local-git": "▣" };

export interface ConnectorPillData {
  name: string;
  packKey: string;
  packTitle: string;
  enabled: boolean;
  unlinked: boolean;
  orgWide: boolean;
  governed: boolean;
  selected: boolean;
  [key: string]: unknown;
}

export function ConnectorPill({ data }: NodeProps) {
  const d = data as ConnectorPillData;
  return (
    <div
      className={`flex items-center gap-2 rounded-sm border px-3 py-2 text-xs shadow-sm ${
        d.selected ? "border-accent bg-accent/10" : "border-border bg-surface"
      } ${!d.enabled || d.unlinked ? "opacity-50" : ""}`}
      title={`${d.packTitle} connector instance`}
    >
      <span className="text-sm text-ink-muted" aria-hidden>
        {PACK_ICONS[d.packKey] ?? "◇"}
      </span>
      <span className="max-w-[140px] truncate font-medium text-ink">{d.name}</span>
      {d.governed && <span title="carries governed actions (gated)">🔒</span>}
      {!d.enabled && (
        <span className="rounded-full bg-danger/15 px-1.5 text-[10px] text-danger">off</span>
      )}
      {d.enabled && d.unlinked && (
        <span className="rounded-full bg-warn/15 px-1.5 text-[10px] text-ink-muted">
          unlinked
        </span>
      )}
      {d.enabled && d.orgWide && (
        <span className="rounded-full bg-surface-2 px-1.5 text-[10px] text-ink-muted">
          org-wide
        </span>
      )}
      <Handle
        type="source"
        id="connector-link"
        position={Position.Right}
        className="!size-2.5 !rounded-full !border-border !bg-canvas"
      />
    </div>
  );
}
