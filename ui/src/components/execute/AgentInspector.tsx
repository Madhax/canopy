// The agent inspector (operator-experience.md §3): "what exactly is this agent doing?" —
// eight tabs over one aggregate, read-only except Intervene and the confirm-gated memory
// reset. `AgentInspector` is presentational (state + callbacks); `InspectorPanel` wires the
// hooks and renders it as a right-side drawer.
import { useState } from "react";
import {
  useAgentState,
  useResetMemory,
  useWorkspaceFile,
  type AgentState,
  type FilePreview,
} from "../../api/inspector";
import { useAssignmentAction, type Assignment, type Gate, type Step } from "../../api/work";
import { Button, CenteredSpinner, EmptyState } from "../common";

const TABS = [
  "Overview", "Assignment", "Plan & Steps", "Spend", "Gates & Queue", "Memory",
  "Session", "Workspace",
] as const;
type Tab = (typeof TABS)[number];

interface Props {
  state: AgentState;
  nodeName: (id: string) => string;
  onClose: () => void;
  onResetMemory: () => void;
  onIntervene: (assignmentId: string, note: string) => void;
  filePreview: FilePreview | null;
  onPreviewFile: (path: string | null) => void;
}

const STATUS_TONE: Record<string, string> = {
  idle: "bg-ink-muted",
  engaged: "bg-accent",
  gated: "bg-warn",
  paused: "bg-warn",
  dead: "bg-danger",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</span>
      <span className="text-xs text-ink">{children}</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-canvas px-3 py-2">
      <div className="text-base font-semibold text-ink">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</div>
    </div>
  );
}

function MeterBar({ spent, allowance, warned }: { spent: number; allowance: number; warned: boolean }) {
  const pct = allowance > 0 ? Math.min(100, Math.round((spent / allowance) * 100)) : 0;
  const tone = pct >= 100 ? "bg-danger" : warned || pct >= 80 ? "bg-warn" : "bg-accent";
  return (
    <div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1 text-[11px] text-ink-muted">
        {spent.toLocaleString()} / {allowance.toLocaleString()} tokens ({pct}%)
      </div>
    </div>
  );
}

function StepsTable({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return <p className="text-xs text-ink-muted">No steps yet.</p>;
  return (
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="text-[10px] uppercase tracking-wide text-ink-muted">
          <th className="py-1 pr-2 font-medium">time</th>
          <th className="py-1 pr-2 font-medium">kind</th>
          <th className="py-1 pr-2 text-right font-medium">in</th>
          <th className="py-1 pr-2 text-right font-medium">out</th>
          <th className="py-1 font-medium">delta</th>
        </tr>
      </thead>
      <tbody>
        {steps.map((s) => (
          <tr key={s.id} className="border-t border-border/60">
            <td className="py-1 pr-2 text-ink-muted">{s.createdAt.slice(11, 19)}</td>
            <td className="py-1 pr-2">{s.kind}</td>
            <td className="py-1 pr-2 text-right">{s.inputTokens.toLocaleString()}</td>
            <td className="py-1 pr-2 text-right">{s.outputTokens.toLocaleString()}</td>
            <td className="py-1 text-ink-muted">
              {s.deltaKind}
              {s.deltaRef ? ` · ${s.deltaRef.slice(0, 40)}` : ""}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function GateRow({ gate }: { gate: Gate }) {
  return (
    <div className="rounded-md border border-border bg-canvas px-3 py-2 text-xs">
      <span className="font-medium text-ink">{gate.kind}</span>
      <span className={`ml-2 ${gate.state === "open" ? "text-warn" : "text-ink-muted"}`}>
        {gate.state}
      </span>
      <span className="ml-2 text-ink-muted">{gate.reason}</span>
      <div className="mt-0.5 text-[10px] text-ink-muted">
        opened by {gate.openedBy} · {gate.createdAt.slice(0, 19).replace("T", " ")}
      </div>
    </div>
  );
}

function AssignmentRow({ a, extra }: { a: Assignment; extra?: string }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-border bg-canvas px-3 py-1.5 text-xs">
      <span className="text-ink">{a.id}</span>
      <span className="text-ink-muted">{a.state}</span>
      {extra !== undefined && <span className="text-ink-muted">{extra}</span>}
    </div>
  );
}

export function AgentInspector({
  state, nodeName, onClose, onResetMemory, onIntervene, filePreview, onPreviewFile,
}: Props) {
  const [tab, setTab] = useState<Tab>("Overview");
  const [confirmReset, setConfirmReset] = useState(false);
  const c = state.charter;
  const cur = state.current;
  const status = state.directory?.status ?? "not-actuated";

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <span className={`h-2 w-2 rounded-full ${STATUS_TONE[status] ?? "bg-ink-muted"}`} />
            {c?.displayName ?? nodeName(state.nodeId)}
            <span className="text-xs font-normal text-ink-muted">{c?.roleKey}</span>
          </h2>
          <p className="text-[11px] text-ink-muted">
            {status}
            {state.directory?.heartbeatAgeSeconds != null &&
              ` · heartbeat ${state.directory.heartbeatAgeSeconds}s ago`}
            {state.actuation && ` · actuation ${state.actuation.state}`}
          </p>
        </div>
        <button className="text-xs text-ink-muted hover:text-ink" onClick={onClose}>
          ✕ close
        </button>
      </header>

      <nav className="flex flex-wrap gap-1 border-b border-border px-3 py-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded px-2 py-1 text-[11px] ${
              tab === t ? "bg-surface-2 font-medium text-ink" : "text-ink-muted hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      <div className="flex-1 overflow-y-auto p-4">
        {tab === "Overview" && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Role">{c ? `${c.roleKey}${c.isManager ? " · manager" : ""}` : "—"}</Field>
              <Field label="Manager">
                {c?.managerNodeId ? nodeName(c.managerNodeId) : "— (root)"}
              </Field>
              <Field label="Reports">
                {c && c.reportNodeIds.length > 0
                  ? c.reportNodeIds.map(nodeName).join(", ")
                  : "none"}
              </Field>
              <Field label="Profile">
                {state.binding
                  ? `${state.binding.name} (${state.binding.provider}/${state.binding.model})`
                  : "unbound"}
              </Field>
              <Field label="Runtime">{state.envelope.runtimeKind}</Field>
              <Field label="Salary">
                {state.salary.perAssignmentAllowance.toLocaleString()} tokens/assignment · warn{" "}
                {state.salary.warnThresholdPct}% · {state.salary.hardStop ? "hard-stop" : "soft"}
              </Field>
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wide text-ink-muted">Grants</span>
              <div className="mt-1 flex flex-wrap gap-1">
                {state.envelope.toolGrants.length === 0 && (
                  <span className="text-xs text-ink-muted">none</span>
                )}
                {state.envelope.toolGrants.map((g) => (
                  <span key={g} className="rounded bg-accent/10 px-1.5 py-0.5 text-[11px] text-ink">
                    {g}
                  </span>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-4 gap-2">
              <Stat label="done" value={String(state.stats.assignmentsDone)} />
              <Stat
                label="accepted"
                value={
                  state.stats.acceptanceRate == null
                    ? "—"
                    : `${Math.round(state.stats.acceptanceRate * 100)}%`
                }
              />
              <Stat
                label="avg cost"
                value={
                  state.stats.avgCostTokens == null
                    ? "—"
                    : state.stats.avgCostTokens.toLocaleString()
                }
              />
              <Stat label="escalations" value={String(state.stats.escalations)} />
            </div>
            {c && (
              <details>
                <summary className="cursor-pointer text-xs text-accent">
                  compiled charter instructions
                </summary>
                <pre className="mt-1 whitespace-pre-wrap rounded-md bg-canvas p-2 text-[11px] text-ink-muted">
                  {c.instructions}
                </pre>
              </details>
            )}
          </div>
        )}

        {tab === "Assignment" &&
          (cur ? (
            <div className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Assignment">{cur.assignment.id}</Field>
                <Field label="State">{cur.assignment.state}</Field>
                <Field label="Contract">
                  {cur.assignment.contractKind}: {cur.assignment.contractType}
                </Field>
                <Field label="Issued by">
                  {cur.assignment.issuedBy === "operator"
                    ? "operator"
                    : nodeName(cur.assignment.issuedBy)}{" "}
                  · intent {cur.assignment.intentId}
                </Field>
              </div>
              <div>
                <span className="text-[10px] uppercase tracking-wide text-ink-muted">
                  Brief ({cur.briefs.length} version{cur.briefs.length === 1 ? "" : "s"})
                </span>
                {cur.briefs.map((b) => (
                  <div key={b.version} className="mt-1 rounded-md border border-border bg-canvas p-2 text-xs">
                    <span className="text-[10px] text-ink-muted">v{b.version}</span>
                    <p className="text-ink">{b.text}</p>
                  </div>
                ))}
              </div>
              {["briefed", "planning", "executing"].includes(cur.assignment.state) && (
                <Button onClick={() => onIntervene(cur.assignment.id, "operator intervention from the inspector")}>
                  Intervene
                </Button>
              )}
            </div>
          ) : (
            <EmptyState title="No active assignment">This agent is idle.</EmptyState>
          ))}

        {tab === "Plan & Steps" &&
          (cur?.plan ? (
            <div className="flex flex-col gap-3">
              <ol className="flex flex-col">
                {cur.plan.stages.map((s) => (
                  <li key={s.idx} className="flex items-center gap-2 text-xs">
                    <span className={s.state === "done" ? "text-ink-muted" : s.state === "active" ? "text-accent" : "text-ink-muted/60"}>
                      {s.state === "done" ? "✓" : s.state === "active" ? "▶" : "○"}
                    </span>
                    <span className={s.state === "active" ? "font-medium text-ink" : "text-ink-muted"}>
                      {s.title}
                    </span>
                    {s.envelopeTokens != null && (
                      <span className="text-[10px] text-ink-muted">
                        env {s.envelopeTokens.toLocaleString()}
                      </span>
                    )}
                  </li>
                ))}
              </ol>
              <StepsTable steps={cur.steps} />
            </div>
          ) : (
            <EmptyState title="No plan yet">Nothing declared for the current assignment.</EmptyState>
          ))}

        {tab === "Spend" && (
          <div className="flex flex-col gap-4">
            {cur?.meter ? (
              <div>
                <span className="text-[10px] uppercase tracking-wide text-ink-muted">
                  Current meter
                </span>
                <MeterBar
                  spent={cur.meter.spent}
                  allowance={cur.meter.allowance}
                  warned={cur.meter.warned}
                />
              </div>
            ) : (
              <p className="text-xs text-ink-muted">No live meter (no active assignment).</p>
            )}
            <div className="grid grid-cols-2 gap-2">
              <Stat label="node tokens" value={state.spend.nodeTokens.toLocaleString()} />
              <Stat label="share of team" value={`${state.spend.sharePct.toFixed(1)}%`} />
            </div>
            {state.history.length > 0 && (
              <div>
                <span className="text-[10px] uppercase tracking-wide text-ink-muted">
                  Past assignments
                </span>
                <div className="mt-1 flex flex-col gap-1">
                  {state.history.map((h) => (
                    <AssignmentRow key={h.id} a={h} extra={`${h.spentTokens.toLocaleString()} tk`} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "Gates & Queue" && (
          <div className="flex flex-col gap-3">
            <span className="text-[10px] uppercase tracking-wide text-ink-muted">
              Open gates {state.gates.open.length > 0 && "— resolve from the inbox"}
            </span>
            {state.gates.open.length === 0 && (
              <p className="text-xs text-ink-muted">No open gates.</p>
            )}
            {state.gates.open.map((g) => (
              <GateRow key={g.id} gate={g} />
            ))}
            {state.queue.length > 0 && (
              <>
                <span className="text-[10px] uppercase tracking-wide text-ink-muted">
                  Queue ({state.queue.length})
                </span>
                {state.queue.map((a) => (
                  <AssignmentRow key={a.id} a={a} extra={`priority ${a.priority}`} />
                ))}
              </>
            )}
            {state.gates.recent.length > 0 && (
              <details>
                <summary className="cursor-pointer text-xs text-accent">
                  {state.gates.recent.length} historical gate{state.gates.recent.length === 1 ? "" : "s"}
                </summary>
                <div className="mt-1 flex flex-col gap-1">
                  {state.gates.recent.map((g) => (
                    <GateRow key={g.id} gate={g} />
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        {tab === "Memory" && (
          <div className="flex flex-col gap-3">
            {state.memory.length === 0 ? (
              <EmptyState title="No memory yet">
                Entries accrue as assignments close.
              </EmptyState>
            ) : (
              state.memory.map((m) => (
                <div key={m.seq} className="rounded-md border border-border bg-canvas p-2 text-xs">
                  <span className="text-[10px] text-ink-muted">
                    #{m.seq} · {m.createdAt.slice(0, 19).replace("T", " ")}
                  </span>
                  <pre className="whitespace-pre-wrap text-[11px] text-ink">
                    {JSON.stringify(m.entry, null, 1)}
                  </pre>
                </div>
              ))
            )}
            {state.memory.length > 0 &&
              (confirmReset ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-danger">
                    Wipe all {state.memory.length} entries? This is the "backfill the position" act.
                  </span>
                  <Button
                    onClick={() => {
                      onResetMemory();
                      setConfirmReset(false);
                    }}
                  >
                    Yes, reset
                  </Button>
                  <button className="text-xs text-ink-muted hover:underline"
                          onClick={() => setConfirmReset(false)}>
                    keep it
                  </button>
                </div>
              ) : (
                <button className="self-start text-xs text-danger hover:underline"
                        onClick={() => setConfirmReset(true)}>
                  Reset memory…
                </button>
              ))}
          </div>
        )}

        {tab === "Session" && (
          <div className="flex flex-col gap-3">
            <Field label="Session ref">
              {state.session.sessionRef ?? "— (no CLI session recorded)"}
            </Field>
            {state.session.transcriptPath && (
              <Field label="Transcript">{state.session.transcriptPath}</Field>
            )}
            <span className="text-[10px] uppercase tracking-wide text-ink-muted">
              Tool calls ({state.session.toolEvents.length})
            </span>
            {state.session.toolEvents.length === 0 && (
              <p className="text-xs text-ink-muted">No tool events.</p>
            )}
            {state.session.toolEvents.map((e) => (
              <div key={e.id} className="flex items-center gap-2 text-xs">
                <span className="text-ink-muted">{e.created_at.slice(11, 19)}</span>
                <span className="text-ink">{e.tool}</span>
                <span className={e.outcome === "denied" ? "text-danger" : "text-ink-muted"}>
                  {e.outcome}
                </span>
              </div>
            ))}
            {state.session.logTail.length > 0 && (
              <details open>
                <summary className="cursor-pointer text-xs text-accent">
                  subprocess log (last {state.session.logTail.length} lines)
                </summary>
                <pre className="mt-1 max-h-64 overflow-y-auto rounded-md bg-canvas p-2 text-[10px] text-ink-muted">
                  {state.session.logTail.join("\n")}
                </pre>
              </details>
            )}
          </div>
        )}

        {tab === "Workspace" &&
          (state.workspace ? (
            <div className="flex flex-col gap-2">
              {state.workspace.truncated && (
                <p className="text-[11px] text-warn">Listing truncated at 500 files.</p>
              )}
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-ink-muted">
                    <th className="py-1 pr-2 font-medium">file</th>
                    <th className="py-1 pr-2 text-right font-medium">size</th>
                    <th className="py-1 font-medium">modified</th>
                  </tr>
                </thead>
                <tbody>
                  {state.workspace.files.map((f) => (
                    <tr key={f.path} className="border-t border-border/60">
                      <td className="py-1 pr-2">
                        <button className="text-accent hover:underline"
                                onClick={() => onPreviewFile(f.path)}>
                          {f.path}
                        </button>
                      </td>
                      <td className="py-1 pr-2 text-right text-ink-muted">
                        {f.size.toLocaleString()}
                      </td>
                      <td className="py-1 text-ink-muted">
                        {f.modifiedAt.slice(0, 19).replace("T", " ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filePreview && (
                <div className="rounded-md border border-border bg-canvas p-2">
                  <div className="mb-1 flex items-center justify-between text-[11px] text-ink-muted">
                    <span>{filePreview.path}</span>
                    <button className="hover:text-ink" onClick={() => onPreviewFile(null)}>
                      ✕
                    </button>
                  </div>
                  {filePreview.content != null ? (
                    <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap text-[11px] text-ink">
                      {filePreview.content}
                    </pre>
                  ) : (
                    <p className="text-xs text-ink-muted">
                      No preview — {filePreview.reason === "binary" ? "binary file" : "over 256 KB"}.
                    </p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <EmptyState title="No workspace">
              The sandbox has not materialized a workspace for this node.
            </EmptyState>
          ))}
      </div>
    </div>
  );
}

/** Wired drawer: fetches the aggregate and renders the panel on the right edge. */
export function InspectorPanel({
  teamId, nodeId, nodeName, onClose,
}: {
  teamId: string;
  nodeId: string;
  nodeName: (id: string) => string;
  onClose: () => void;
}) {
  const state = useAgentState(teamId, nodeId);
  const reset = useResetMemory(teamId);
  const act = useAssignmentAction(teamId);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const preview = useWorkspaceFile(teamId, nodeId, previewPath);

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-[460px] max-w-full border-l border-border bg-surface shadow-xl">
      {state.data ? (
        <AgentInspector
          state={state.data}
          nodeName={nodeName}
          onClose={onClose}
          onResetMemory={() => reset.mutate(nodeId)}
          onIntervene={(assignmentId, note) =>
            act.mutate({ assignmentId, action: "intervene", body: { note } })
          }
          filePreview={preview.data ?? null}
          onPreviewFile={setPreviewPath}
        />
      ) : state.isError ? (
        <div className="p-4">
          <EmptyState title="Inspector unavailable">
            {(state.error as Error).message}
          </EmptyState>
          <button className="mt-2 text-xs text-accent hover:underline" onClick={onClose}>
            close
          </button>
        </div>
      ) : (
        <CenteredSpinner label="Inspecting…" />
      )}
    </div>
  );
}
