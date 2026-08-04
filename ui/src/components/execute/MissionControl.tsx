// Mission control (operator-experience.md §2): "what is my organization doing?" — the org
// pulse header (always visible in every Operate view) and the chart projected as a live tree
// of node cards with the operations overlay: status, current work, queue/WIP, meter, gate
// padlocks, runtime kind. Every card deep-links into the inspector.
import type { Pulse, PulseNode } from "../../api/pulse";
import { EmptyState } from "../common";

const STATUS_TONE: Record<string, string> = {
  idle: "bg-ok/15 text-ok",
  engaged: "bg-accent/15 text-accent",
  gated: "bg-warn/15 text-warn",
  paused: "bg-warn/15 text-warn",
  booting: "bg-warn/15 text-warn",
  provisioning: "bg-warn/15 text-warn",
  pending: "bg-warn/15 text-warn",
  failed: "bg-danger/15 text-danger",
  dead: "bg-danger/15 text-danger",
  "not-actuated": "bg-surface-2 text-ink-muted",
};

const ACTUATION_TONE: Record<string, string> = {
  live: "bg-ok/15 text-ok",
  degraded: "bg-warn/15 text-warn",
  stopped: "bg-surface-2 text-ink-muted",
  provisioning: "bg-warn/15 text-warn",
};

function fmtCost(micros: number): string {
  return `$${(micros / 1_000_000).toFixed(micros >= 10_000_000 ? 2 : 4)}`;
}

/** The always-visible observability strip: actuation · intents · burn · gates · attention. */
export function OrgPulse({ pulse }: { pulse: Pulse }) {
  const actuation = pulse.actuation?.state ?? "not actuated";
  const gateSummary = Object.entries(pulse.gates.byKind)
    .map(([k, n]) => `${n} ${k}`)
    .join(" · ");
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border bg-surface px-6 py-1.5 text-xs">
      <span
        className={`rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${
          ACTUATION_TONE[actuation] ?? "bg-surface-2 text-ink-muted"
        }`}
      >
        {actuation}
      </span>
      <span className="text-ink-muted">
        <span className="font-semibold text-ink">{pulse.intents.open}</span> open intent
        {pulse.intents.open === 1 ? "" : "s"}
      </span>
      <span
        className="text-ink-muted"
        title={`over the last ${pulse.burn.windowMinutes} min · costs are estimates`}
      >
        burn{" "}
        <span className="font-semibold text-ink">
          {Math.round(pulse.burn.tokensPerMinute).toLocaleString()}
        </span>{" "}
        tk/min · ~{fmtCost(pulse.burn.estCostMicrosPerHour)}/hr
      </span>
      <span className="text-ink-muted">
        <span className="font-semibold text-ink">{pulse.gates.open}</span> open gate
        {pulse.gates.open === 1 ? "" : "s"}
        {gateSummary && <span className="ml-1 text-[11px]">({gateSummary})</span>}
      </span>
      {pulse.gates.attention > 0 && (
        <span className="rounded-full bg-danger/15 px-2 py-0.5 text-[11px] font-medium text-danger">
          {pulse.gates.attention} need you
        </span>
      )}
    </div>
  );
}

function MeterArc({ meter }: { meter: NonNullable<PulseNode["meter"]> }) {
  const pct =
    meter.allowance > 0 ? Math.min(100, Math.round((meter.spent / meter.allowance) * 100)) : 0;
  const tone =
    meter.state === "stopped" || pct >= 100
      ? "bg-danger"
      : meter.warned || pct >= 80
        ? "bg-warn"
        : "bg-ok";
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] text-ink-muted"
      title={`${meter.spent.toLocaleString()}/${meter.allowance.toLocaleString()} tokens`}
    >
      <span className="inline-block h-1 w-12 overflow-hidden rounded-full bg-surface-2">
        <span className={`block h-full ${tone}`} style={{ width: `${pct}%` }} />
      </span>
      {pct}%
    </span>
  );
}

function NodeCard({ node, onInspect }: { node: PulseNode; onInspect: (id: string) => void }) {
  const dim = node.status === "idle" || node.status === "not-actuated";
  return (
    <button
      onClick={() => onInspect(node.nodeId)}
      title="Inspect this agent"
      className={`w-[230px] rounded-md border border-border bg-surface p-2 text-left shadow-sm transition-shadow hover:border-accent hover:shadow-md ${
        dim ? "opacity-70" : ""
      }`}
    >
      <div className="flex items-center gap-1.5">
        <span className="truncate text-xs font-semibold text-ink">{node.name}</span>
        <span
          className={`ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide ${
            STATUS_TONE[node.status] ?? "bg-surface-2 text-ink-muted"
          }`}
        >
          {node.status}
        </span>
      </div>
      <div className="truncate text-[10px] uppercase tracking-wide text-ink-muted">
        {node.roleKey} · {node.runtimeKind}
      </div>
      {node.current ? (
        <p className="mt-1 truncate text-[11px] text-ink" title={node.current.briefPreview}>
          <span className="text-accent">{node.current.state}</span> · {node.current.briefPreview}
        </p>
      ) : (
        <p className="mt-1 text-[11px] text-ink-muted">no active work</p>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {node.meter && <MeterArc meter={node.meter} />}
        {node.queueDepth > 0 && (
          <span className="text-[10px] text-ink-muted">queue {node.queueDepth}</span>
        )}
        {node.wip > 1 && <span className="text-[10px] text-ink-muted">wip {node.wip}</span>}
        {node.openGateKinds.map((k, i) => (
          <span key={`${k}${i}`} className="rounded bg-warn/15 px-1 text-[10px] text-warn">
            🔒 {k}
          </span>
        ))}
      </div>
    </button>
  );
}

/** The chart as a live tree: managers above their reports, every card an inspect handle. */
export function MissionControl({
  pulse,
  onInspect,
}: {
  pulse: Pulse;
  onInspect: (nodeId: string) => void;
}) {
  if (pulse.nodes.length === 0) {
    return <EmptyState title="No agents">Build the chart in the editor first.</EmptyState>;
  }
  const byManager = new Map<string | null, PulseNode[]>();
  for (const n of pulse.nodes) {
    const list = byManager.get(n.managerId) ?? [];
    list.push(n);
    byManager.set(n.managerId, list);
  }
  const known = new Set(pulse.nodes.map((n) => n.nodeId));
  const roots = pulse.nodes.filter((n) => n.managerId === null || !known.has(n.managerId));

  const renderTier = (nodes: PulseNode[]): React.ReactNode => (
    <div className="flex flex-col items-center gap-3">
      <div className="flex flex-wrap justify-center gap-3">
        {nodes.map((n) => (
          <NodeCard key={n.nodeId} node={n} onInspect={onInspect} />
        ))}
      </div>
      {(() => {
        const children = nodes.flatMap((n) => byManager.get(n.nodeId) ?? []);
        return children.length > 0 ? (
          <div className="w-full border-t border-dashed border-border pt-3">
            {renderTier(children)}
          </div>
        ) : null;
      })()}
    </div>
  );

  return <div className="py-2">{renderTier(roots)}</div>;
}
