// Mission control (operator-experience.md §2): "what is my team doing?" — the team
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

// F5: "delivering" is finished work waiting on its REVIEWER — showing the raw state read as
// "stuck" during the live run. Label states in operator language wherever they render.
export const STATE_LABEL: Record<string, string> = {
  delivering: "awaiting review",
};

export const stateLabel = (s: string) => STATE_LABEL[s] ?? s;

/** F5: one line of narrative — what the team is doing and whether any of it needs you. */
export function pulseNarrative(pulse: Pulse, opts?: { includeAttention?: boolean }): string {
  const parts: string[] = [];
  const working = pulse.nodes.filter(
    (n) => n.current && ["planning", "executing", "intake", "briefed"].includes(n.current.state),
  ).length;
  const reviewing = pulse.nodes.filter((n) => n.current?.state === "delivering").length;
  if (working > 0) parts.push(`${working} working`);
  if (reviewing > 0) parts.push(`${reviewing} awaiting review`);
  if (parts.length === 0 && pulse.intents.open === 0) parts.push("no open work");
  if (opts?.includeAttention === false) return parts.join(" · ");
  parts.push(pulse.gates.attention > 0
    ? `${pulse.gates.attention} need${pulse.gates.attention === 1 ? "s" : ""} you`
    : "nothing needs you");
  return parts.join(" · ");
}

/** The always-visible observability strip: actuation · intents · burn · gates · attention. */
export function TeamPulse({ pulse }: { pulse: Pulse }) {
  const actuation = pulse.actuation?.state ?? "not actuated";
  const internal = pulse.gates.open - pulse.gates.attention;
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
      {/* F5: operator gates and internal wiring are different facts — only one is your job. */}
      {internal > 0 && (
        <span className="text-ink-muted" title={gateSummary}>
          <span className="font-semibold text-ink">{internal}</span> internal gate
          {internal === 1 ? "" : "s"} (wiring)
        </span>
      )}
      <span className="text-ink-muted">
        {pulseNarrative(pulse, { includeAttention: pulse.gates.attention === 0 })}
      </span>
      {/* F4: the single most urgent fact is unmissable, not a rail item. */}
      {pulse.gates.attention > 0 && (
        <span className="animate-pulse rounded-full bg-danger/15 px-2 py-0.5 text-[11px] font-semibold text-danger">
          {pulse.gates.attention} gate{pulse.gates.attention === 1 ? "" : "s"} need
          {pulse.gates.attention === 1 ? "s" : ""} you
        </span>
      )}
    </div>
  );
}

// F15: the budget meter is a separate, LABELED affordance — the bare arc read as "progress"
// and sat at ~0% all run with six-figure allowances.
export function BudgetChip({ meter }: { meter: NonNullable<PulseNode["meter"]> }) {
  const pct = meter.allowance > 0 ? (meter.spent / meter.allowance) * 100 : 0;
  const tone =
    meter.state === "stopped" || pct >= 100
      ? "text-danger"
      : meter.warned || pct >= 80
        ? "text-warn"
        : "text-ink-muted";
  return (
    <span
      className={`text-[10px] ${tone}`}
      title={`budget: ${meter.spent.toLocaleString()}/${meter.allowance.toLocaleString()} tokens`}
    >
      budget {pct >= 10 ? Math.round(pct) : pct.toFixed(1)}%
    </span>
  );
}

/** F15: completed stages over the plan — the primary progress number per assignment. */
export function StageProgress({ progress }: { progress: { done: number; total: number } }) {
  const pct = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] text-ink-muted"
      title={`${progress.done} of ${progress.total} plan stages done`}
    >
      <span className="inline-block h-1 w-12 overflow-hidden rounded-full bg-surface-2">
        <span className="block h-full bg-accent" style={{ width: `${pct}%` }} />
      </span>
      {progress.done}/{progress.total} stages
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
          <span className={node.current.state === "delivering" ? "text-warn" : "text-accent"}>
            {stateLabel(node.current.state)}
          </span>{" "}
          · {node.current.briefPreview}
        </p>
      ) : (
        <p className="mt-1 text-[11px] text-ink-muted">no active work</p>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {node.current?.stageProgress && <StageProgress progress={node.current.stageProgress} />}
        {node.meter && <BudgetChip meter={node.meter} />}
        {node.queueDepth > 0 && (
          <span className="text-[10px] text-ink-muted">queue {node.queueDepth}</span>
        )}
        {node.wip > 1 && <span className="text-[10px] text-ink-muted">wip {node.wip}</span>}
        {/* F5: operator-owned gates ring; internal wiring (dependency/await) stays quiet. */}
        {(node.openGates ?? node.openGateKinds.map((k) => ({ kind: k, owner: "operator" }))).map(
          (g, i) =>
            g.owner === "operator" ? (
              <span key={`${g.kind}${i}`}
                    className="rounded bg-danger/15 px-1 text-[10px] font-medium text-danger">
                🔒 {g.kind}
              </span>
            ) : (
              <span key={`${g.kind}${i}`}
                    className="rounded bg-surface-2 px-1 text-[10px] text-ink-muted"
                    title={`${g.kind} gate — internal (${g.owner}), not your action`}>
                🔗 {g.kind}
              </span>
            ),
        )}
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
