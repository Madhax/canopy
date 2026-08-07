// The cost explorer (E5 part 2b, operator-experience.md §6): where the money went, read from
// the extended spend rollups — by intent with the coordination/production split (SC-1: overhead
// is measured, not hidden), by node with acceptance and rework alongside (cost without quality
// context invites the wrong conclusions). Every number drills down: intent → assignments → steps.
// Costs are labeled estimates (risk IM-5); token counts are provider-authoritative.
import { useState } from "react";
import type { Assignment, Intent, SpendRow, Step } from "../../api/work";
import { useAssignmentDetail, useAssignments, useIntents, useSpend } from "../../api/work";

const fmtTokens = (n: number) => n.toLocaleString();
const fmtCost = (micros: number) => `$${(micros / 1_000_000).toFixed(4)}`;

/** F2: a zero estimate over real tokens means "no price configured", never "$0.0000" —
 * IM-5's honesty rule at the display layer. */
const fmtCostHonest = (micros: number, tokens: number) =>
  micros === 0 && tokens > 0 ? "—" : fmtCost(micros);

/** Coordination vs production as one stacked bar — the SC-1 split at a glance.
 * Labeled "% coord" (F2): the bare percentage read as share-of-total spend. */
function SplitBar({ coordination, production }: { coordination: number; production: number }) {
  const total = coordination + production;
  const pct = total > 0 ? Math.round((coordination / total) * 100) : 0;
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] text-ink-muted"
      title={`${fmtTokens(coordination)} coordination / ${fmtTokens(production)} production tokens`}
    >
      <span className="inline-flex h-1.5 w-20 overflow-hidden rounded-full bg-surface-2">
        <span className="block h-full bg-warn" style={{ width: `${pct}%` }} />
        <span className="block h-full bg-accent" style={{ width: `${100 - pct}%` }} />
      </span>
      {pct}% coord
    </span>
  );
}

function StepsTable({ steps }: { steps: Step[] }) {
  if (steps.length === 0)
    return <p className="py-1 text-[11px] text-ink-muted">No steps recorded yet.</p>;
  return (
    <table className="w-full text-[11px]">
      <thead>
        <tr className="text-left text-ink-muted">
          <th className="py-0.5 pr-2 font-normal">step</th>
          <th className="py-0.5 pr-2 font-normal">kind</th>
          <th className="py-0.5 pr-2 font-normal">delta</th>
          <th className="py-0.5 pr-2 text-right font-normal">in</th>
          <th className="py-0.5 pr-2 text-right font-normal">out</th>
          <th className="py-0.5 text-right font-normal">cached</th>
        </tr>
      </thead>
      <tbody>
        {steps.map((s) => (
          <tr key={s.id} className="border-t border-border/50 text-ink">
            <td className="py-0.5 pr-2 font-mono text-ink-muted">{s.id.slice(0, 10)}…</td>
            <td className="py-0.5 pr-2">{s.kind}</td>
            <td className="py-0.5 pr-2 text-ink-muted">{s.deltaKind}</td>
            <td className="py-0.5 pr-2 text-right">{fmtTokens(s.inputTokens)}</td>
            <td className="py-0.5 pr-2 text-right">{fmtTokens(s.outputTokens)}</td>
            <td className="py-0.5 text-right text-ink-muted">
              {fmtTokens((s.cacheReadTokens ?? 0) + (s.cacheCreationTokens ?? 0))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export interface CostExplorerProps {
  byIntent: SpendRow[];
  byNode: SpendRow[];
  byAssignment: SpendRow[];
  intents: Intent[];
  assignments: Assignment[];
  nodeName: (id: string) => string;
  /** Steps for the one open assignment drill; null while loading / nothing open. */
  openAssignmentId: string | null;
  openAssignmentSteps: Step[] | null;
  onToggleSteps: (assignmentId: string) => void;
}

/** Presentational: every number is a projection of the spend feed; the view stores nothing. */
export function CostExplorer(props: CostExplorerProps) {
  const { byIntent, byNode, byAssignment, intents, assignments, nodeName } = props;
  const [openIntent, setOpenIntent] = useState<string | null>(null);

  const intentText = new Map(intents.map((i) => [i.id, i.text]));
  const spendByAssignment = new Map(byAssignment.map((r) => [r.key, r]));

  const totals = byIntent.reduce(
    (t, r) => ({
      cost: t.cost + r.est_cost_micros,
      tokens: t.tokens + r.input_tokens + r.output_tokens,
      cached: t.cached + (r.cache_read_tokens ?? 0) + (r.cache_creation_tokens ?? 0),
      steps: t.steps + r.steps,
      coord: t.coord + (r.coordination_tokens ?? 0),
      prod: t.prod + (r.production_tokens ?? 0),
    }),
    { cost: 0, tokens: 0, cached: 0, steps: 0, coord: 0, prod: 0 },
  );
  const totalOverhead =
    totals.coord + totals.prod > 0
      ? Math.round((totals.coord / (totals.coord + totals.prod)) * 100)
      : null;
  // F2: every recorded cost being zero while tokens flowed means the model has no price row —
  // say so instead of quoting $0.0000 (the run's "everything is free" confusion).
  const priceMissing = totals.cost === 0 && totals.tokens > 0;

  // Quality context per node, derived from the assignment list (accepted|closed = accepted).
  const nodeStats = new Map<string, { total: number; accepted: number; terminal: number; rework: number }>();
  for (const a of assignments) {
    const s = nodeStats.get(a.nodeId) ?? { total: 0, accepted: 0, terminal: 0, rework: 0 };
    s.total += 1;
    if (a.state === "accepted" || a.state === "closed") {
      s.accepted += 1;
      s.terminal += 1;
    } else if (a.state === "cancelled" || a.state === "failed") {
      s.terminal += 1;
    }
    s.rework += Math.max(0, a.briefVersion - 1);
    nodeStats.set(a.nodeId, s);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Headline: the whole engagement's burn, overhead first-class */}
      <section className="grid grid-cols-4 gap-3">
        {[
          {
            label: "Est. cost",
            value: priceMissing ? "—" : fmtCost(totals.cost),
            sub: priceMissing ? "no price for this model — tokens only" : null,
          },
          {
            label: "Tokens",
            value: fmtTokens(totals.tokens),
            sub: totals.cached > 0 ? `+ ${fmtTokens(totals.cached)} cached context` : null,
          },
          { label: "Steps", value: fmtTokens(totals.steps), sub: null },
          {
            label: "Overhead",
            value: totalOverhead === null ? "—" : `${totalOverhead}%`,
            sub: null,
          },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border border-border bg-surface px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-ink-muted">{s.label}</p>
            <p className="text-lg font-semibold text-ink">{s.value}</p>
            {s.sub ? <p className="text-[11px] text-ink-muted">{s.sub}</p> : null}
          </div>
        ))}
      </section>

      {/* By intent: what each ask actually cost */}
      <section className="rounded-lg border border-border bg-surface p-4">
        <h2 className="mb-2 text-sm font-semibold text-ink">By intent</h2>
        {byIntent.length === 0 ? (
          <p className="text-xs text-ink-muted">No spend yet.</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-ink-muted">
                <th className="py-1 pr-2 font-normal">intent</th>
                <th className="py-1 pr-2 font-normal">split</th>
                <th className="py-1 pr-2 text-right font-normal">tokens</th>
                <th className="py-1 pr-2 text-right font-normal">steps</th>
                <th className="py-1 text-right font-normal">est. cost</th>
              </tr>
            </thead>
            <tbody>
              {byIntent.map((r) => {
                const label = intentText.get(r.key) ?? r.key;
                const children = assignments.filter((a) => a.intentId === r.key);
                const open = openIntent === r.key;
                return [
                  <tr key={r.key} className="border-t border-border">
                    <td className="max-w-[280px] truncate py-1.5 pr-2">
                      <button
                        className="text-left text-ink hover:text-accent"
                        title={label}
                        onClick={() => setOpenIntent(open ? null : r.key)}
                      >
                        <span className="mr-1 text-ink-muted">{open ? "▾" : "▸"}</span>
                        {label}
                      </button>
                    </td>
                    <td className="py-1.5 pr-2">
                      <SplitBar
                        coordination={r.coordination_tokens ?? 0}
                        production={r.production_tokens ?? 0}
                      />
                    </td>
                    <td className="py-1.5 pr-2 text-right text-ink">
                      {fmtTokens(r.input_tokens + r.output_tokens)}
                    </td>
                    <td className="py-1.5 pr-2 text-right text-ink">{r.steps}</td>
                    <td className="py-1.5 text-right font-medium text-ink">
                      {fmtCostHonest(r.est_cost_micros, r.input_tokens + r.output_tokens)}
                    </td>
                  </tr>,
                  ...(open
                    ? children.map((a) => {
                        const spend = spendByAssignment.get(a.id);
                        const stepsOpen = props.openAssignmentId === a.id;
                        return (
                          <tr key={a.id} className="border-t border-border/50 bg-canvas/50">
                            <td className="py-1 pl-6 pr-2" colSpan={2}>
                              <button
                                className="text-ink hover:text-accent"
                                onClick={() => props.onToggleSteps(a.id)}
                              >
                                <span className="mr-1 text-ink-muted">{stepsOpen ? "▾" : "▸"}</span>
                                {nodeName(a.nodeId)}
                              </button>
                              <span className="ml-2 text-ink-muted">{a.state}</span>
                              {a.briefVersion > 1 && (
                                <span className="ml-2 rounded bg-warn/15 px-1.5 text-[10px] text-warn">
                                  rework · brief v{a.briefVersion}
                                </span>
                              )}
                              {stepsOpen && (
                                <div className="mt-1 rounded border border-border/50 bg-surface p-2">
                                  {props.openAssignmentSteps === null ? (
                                    <p className="text-[11px] text-ink-muted">Loading steps…</p>
                                  ) : (
                                    <StepsTable steps={props.openAssignmentSteps} />
                                  )}
                                </div>
                              )}
                            </td>
                            <td className="py-1 pr-2 text-right text-ink-muted">
                              {spend ? fmtTokens(spend.input_tokens + spend.output_tokens) : "—"}
                            </td>
                            <td className="py-1 pr-2 text-right text-ink-muted">
                              {spend ? spend.steps : "—"}
                            </td>
                            <td className="py-1 text-right text-ink-muted">
                              {spend
                                ? fmtCostHonest(
                                    spend.est_cost_micros,
                                    spend.input_tokens + spend.output_tokens,
                                  )
                                : "—"}
                            </td>
                          </tr>
                        );
                      })
                    : []),
                ];
              })}
            </tbody>
          </table>
        )}
      </section>

      {/* By node: spend ranking with quality context alongside */}
      <section className="rounded-lg border border-border bg-surface p-4">
        <h2 className="mb-2 text-sm font-semibold text-ink">By node</h2>
        {byNode.length === 0 ? (
          <p className="text-xs text-ink-muted">No spend yet.</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-ink-muted">
                <th className="py-1 pr-2 font-normal">node</th>
                <th className="py-1 pr-2 font-normal">split</th>
                <th className="py-1 pr-2 text-right font-normal">tokens</th>
                <th className="py-1 pr-2 text-right font-normal">accepted</th>
                <th className="py-1 pr-2 text-right font-normal">rework</th>
                <th className="py-1 text-right font-normal">est. cost</th>
              </tr>
            </thead>
            <tbody>
              {byNode.map((r) => {
                const s = nodeStats.get(r.key);
                return (
                  <tr key={r.key} className="border-t border-border">
                    <td className="py-1.5 pr-2 text-ink">{nodeName(r.key)}</td>
                    <td className="py-1.5 pr-2">
                      <SplitBar
                        coordination={r.coordination_tokens ?? 0}
                        production={r.production_tokens ?? 0}
                      />
                    </td>
                    <td className="py-1.5 pr-2 text-right text-ink">
                      {fmtTokens(r.input_tokens + r.output_tokens)}
                    </td>
                    <td className="py-1.5 pr-2 text-right text-ink">
                      {s && s.terminal > 0 ? `${s.accepted}/${s.terminal}` : "—"}
                    </td>
                    <td className="py-1.5 pr-2 text-right">
                      {s && s.rework > 0 ? (
                        <span className="text-warn">{s.rework}</span>
                      ) : (
                        <span className="text-ink-muted">0</span>
                      )}
                    </td>
                    <td className="py-1.5 text-right font-medium text-ink">
                      {fmtCostHonest(r.est_cost_micros, r.input_tokens + r.output_tokens)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <p className="text-[11px] text-ink-muted">
        Costs are estimates (provider-reported tokens × configured rates) — risk IM-5. A “—”
        cost over real tokens means the model has no price row in canopy.toml.
      </p>
    </div>
  );
}

/** Container: wires the spend feed + assignment list; one steps drill open at a time. */
export function CostSection({
  orgId,
  nodeName,
}: {
  orgId: string | null;
  nodeName: (id: string) => string;
}) {
  const byIntent = useSpend(orgId, "intent");
  const byNode = useSpend(orgId, "node");
  const byAssignment = useSpend(orgId, "assignment");
  const intents = useIntents(orgId);
  const assignments = useAssignments(orgId);
  const [openAssignmentId, setOpenAssignmentId] = useState<string | null>(null);
  const detail = useAssignmentDetail(openAssignmentId);

  return (
    <CostExplorer
      byIntent={byIntent.data ?? []}
      byNode={byNode.data ?? []}
      byAssignment={byAssignment.data ?? []}
      intents={intents.data ?? []}
      assignments={assignments.data ?? []}
      nodeName={nodeName}
      openAssignmentId={openAssignmentId}
      openAssignmentSteps={detail.data?.steps ?? null}
      onToggleSteps={(id) => setOpenAssignmentId((cur) => (cur === id ? null : id))}
    />
  );
}
