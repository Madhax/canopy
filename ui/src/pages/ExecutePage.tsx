// Phase 3 · Execute — the operator work surface (E5 part 1): submit intents, review the
// staged fan-out, read the living plan, and clear the inbox. Everything here is the E2/E3
// engine API, kept fresh by the SSE channel (events.ts) with polling as the fallback.
import { useMemo, useState } from "react";
import { useCatalog } from "../api/catalog";
import { useOrgEvents } from "../api/events";
import { useOrganizations } from "../api/organizations";
import {
  useAssignmentAction,
  useIntentPlan,
  useIntents,
  useLeaveNote,
  useMarkNotificationsRead,
  useNotifications,
  useOperatorGates,
  useResolveGate,
  useSubmitIntent,
} from "../api/work";
import { apiGet } from "../api/client";
import { useQuery } from "@tanstack/react-query";
import { usePulse } from "../api/pulse";
import { useAssignments } from "../api/work";
import { Button, CenteredSpinner, EmptyState, Markdown } from "../components/common";
import { InspectorPanel } from "../components/execute/AgentInspector";
import { CadenceSection, type CadenceSeed } from "../components/execute/CadenceSection";
import { CostSection } from "../components/execute/CostExplorer";
import { MissionControl, OrgPulse } from "../components/execute/MissionControl";
import { GateCard } from "../components/execute/GateCard";
import { OrgPicker, orgLabelSuffix } from "../components/execute/OrgPicker";
import { PlanOutline } from "../components/execute/PlanOutline";

const SEVERITY_TONE: Record<string, string> = {
  attention: "border-danger/40 bg-danger/5",
  warning: "border-warn/40 bg-warn/5",
  info: "border-border bg-surface",
};

function useOrgDoc(orgId: string | null) {
  return useQuery({
    queryKey: ["org-doc", orgId],
    queryFn: () => apiGet<{ agents: { id: string; name: string }[] }>(`/organizations/${orgId}`),
    enabled: !!orgId,
    staleTime: 60_000,
  });
}

export function ExecutePage() {
  const orgs = useOrganizations();
  useCatalog(); // warm the cache for names elsewhere
  // F5: no default org — landing is the actuated-org picker, not org[0]'s (possibly dead)
  // console. The header select stays as the switcher once an org is chosen.
  const [orgId, setOrgId] = useState<string | null>(null);
  const effectiveOrg = orgId;
  const [intentId, setIntentId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [view, setView] = useState<"work" | "pulse" | "costs">("work");
  const [inspectNode, setInspectNode] = useState<string | null>(null);
  const [cadenceSeed, setCadenceSeed] = useState<CadenceSeed | null>(null);

  const live = useOrgEvents(effectiveOrg);
  const pulse = usePulse(effectiveOrg);
  const intents = useIntents(effectiveOrg);
  const gates = useOperatorGates(effectiveOrg);
  const notifications = useNotifications(effectiveOrg);
  const orgDoc = useOrgDoc(effectiveOrg);
  const submit = useSubmitIntent(effectiveOrg);
  const resolve = useResolveGate(effectiveOrg);
  const act = useAssignmentAction(effectiveOrg);
  const leaveNote = useLeaveNote(effectiveOrg);
  const markRead = useMarkNotificationsRead(effectiveOrg);

  const effectiveIntent = intentId ?? intents.data?.[0]?.id ?? null;
  const plan = useIntentPlan(effectiveIntent);
  const assignments = useAssignments(effectiveOrg);

  const nodeName = useMemo(() => {
    const byId = new Map((orgDoc.data?.agents ?? []).map((a) => [a.id, a.name]));
    return (id: string) => byId.get(id) ?? id;
  }, [orgDoc.data]);

  // F4: intents whose tree holds an open operator gate get the attention ring on their chip.
  const intentsNeedingYou = useMemo(() => {
    const intentOf = new Map((assignments.data ?? []).map((a) => [a.id, a.intentId]));
    const set = new Set<string>();
    for (const g of gates.data ?? []) {
      const iid = intentOf.get(g.assignmentId);
      if (iid) set.add(iid);
    }
    return set;
  }, [assignments.data, gates.data]);

  const orgSuffix = useMemo(() => orgLabelSuffix(orgs.data ?? []), [orgs.data]);

  return (
    <div className="min-h-full">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <div>
          <h1 className="text-base font-semibold text-ink">Execute</h1>
          <p className="text-xs text-ink-muted">
            Phase 3 · Execute — give the organization work and govern it through gates
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* F4: the count of gates blocking this org is header-level, not a rail footnote. */}
          {effectiveOrg && (gates.data?.length ?? 0) > 0 && (
            <button
              onClick={() => setView("work")}
              title="Open gates need your decision — click to see them"
              className="animate-pulse rounded-full bg-danger/15 px-2.5 py-1 text-[11px] font-semibold text-danger"
            >
              🔒 {gates.data!.length} gate{gates.data!.length === 1 ? "" : "s"} need
              {gates.data!.length === 1 ? "s" : ""} you
            </button>
          )}
          <span
            className={`flex items-center gap-1.5 text-[11px] ${live ? "text-ok" : "text-ink-muted"}`}
            title={live ? "Live over SSE" : "Stream down — polling every 2.5s"}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-ok" : "bg-ink-muted"}`} />
            {live ? "live" : "polling"}
          </span>
          <div className="flex rounded-md border border-border bg-canvas p-0.5 text-xs">
            {(["work", "pulse", "costs"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded px-2.5 py-1 capitalize ${
                  view === v ? "bg-surface font-medium text-ink shadow-sm" : "text-ink-muted"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
          <select
            value={effectiveOrg ?? ""}
            onChange={(e) => {
              setOrgId(e.target.value || null);
              setIntentId(null);
              setInspectNode(null);
            }}
            className="rounded-md border border-border bg-canvas px-2 py-1 text-sm outline-none focus:border-accent"
          >
            <option value="">— pick an organization —</option>
            {(orgs.data ?? []).map((o) => (
              <option key={o.id} value={o.id}>
                {orgSuffix(o.id) ? `${o.name} ${orgSuffix(o.id)}` : o.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      {effectiveOrg && pulse.data && <OrgPulse pulse={pulse.data} />}

      {orgs.isLoading ? (
        <CenteredSpinner label="Loading organizations…" />
      ) : !effectiveOrg ? (
        <OrgPicker orgs={orgs.data ?? []} onPick={setOrgId} />
      ) : view === "costs" ? (
        <main className="mx-auto max-w-6xl px-6 py-6">
          <CostSection orgId={effectiveOrg} nodeName={nodeName} />
        </main>
      ) : view === "pulse" ? (
        <main className="mx-auto max-w-6xl px-6 py-6">
          {pulse.data ? (
            <>
              <MissionControl pulse={pulse.data} onInspect={setInspectNode} />
              {pulse.data.intents.open === 0 && (
                <p className="mt-4 text-center text-xs text-ink-muted">
                  No open intents — give the org work from the{" "}
                  <button className="text-accent hover:underline" onClick={() => setView("work")}>
                    work view
                  </button>
                  .
                </p>
              )}
            </>
          ) : (
            <CenteredSpinner label="Reading the pulse…" />
          )}
        </main>
      ) : (
        <main className="mx-auto grid max-w-6xl grid-cols-[1fr_320px] gap-6 px-6 py-6">
          <div className="flex flex-col gap-6">
            {/* F4: open gates ARE the main column's first content — the operator's single
                most urgent action must not sit in a side rail. */}
            {(gates.data ?? []).length > 0 && (
              <section className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-danger">
                  Needs your decision — the org is blocked on these
                </h2>
                {(gates.data ?? []).map((g) => (
                  <GateCard
                    key={g.id}
                    gate={g}
                    nodeName={nodeName}
                    busy={resolve.isPending}
                    onResolve={(gateId, body) => resolve.mutate({ gateId, body })}
                  />
                ))}
              </section>
            )}

            {/* Intent console. F6: a real intent is paragraphs of markdown, not one line. */}
            <section>
              <form
                className="mb-3 flex items-end gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (text.trim()) submit.mutate({ text: text.trim() });
                  setText("");
                }}
              >
                <textarea
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    e.target.style.height = "auto";
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 320)}px`;
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && text.trim()) {
                      e.preventDefault();
                      submit.mutate({ text: text.trim() });
                      setText("");
                    }
                  }}
                  rows={2}
                  placeholder={'Give the org work — e.g. "Add CSV export; all tests must pass". Markdown welcome; Ctrl+Enter submits.'}
                  className="flex-1 resize-none rounded-md border border-border bg-canvas px-3 py-2 text-sm outline-none focus:border-accent"
                />
                <Button type="submit" disabled={submit.isPending || !text.trim()}>
                  Submit intent
                </Button>
              </form>
              {submit.isError && (
                <p className="mb-2 text-xs text-danger">
                  {(submit.error as Error).message} — is the organization actuated?
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {(intents.data ?? []).map((i) => {
                  // F6: chips show the intent's first line, not a mid-paragraph slice.
                  const firstLine = i.text.split("\n")[0].replace(/^#+\s*/, "");
                  // F4: an intent whose tree holds an open operator gate rings.
                  const needsYou = intentsNeedingYou.has(i.id);
                  return (
                  <span key={i.id} className="flex items-center gap-1">
                    <button
                      onClick={() => setIntentId(i.id)}
                      className={`rounded-full border px-3 py-1 text-xs ${
                        needsYou
                          ? "border-danger bg-danger/10 text-ink"
                          : i.id === effectiveIntent
                            ? "border-accent bg-accent/10 text-ink"
                            : "border-border bg-surface text-ink-muted hover:border-accent"
                      } ${i.id === effectiveIntent && needsYou ? "ring-1 ring-danger" : ""}`}
                    >
                      {needsYou && (
                        <span className="mr-1" title="A gate in this intent needs you">
                          🔒
                        </span>
                      )}
                      {i.cadenceId && (
                        <span className="mr-1" title="Fired by a cadence">
                          ↻
                        </span>
                      )}
                      {firstLine.slice(0, 48)}
                      {firstLine.length > 48 ? "…" : ""}
                      <span className="ml-1 text-[10px] uppercase">{i.state}</span>
                    </button>
                    {i.state === "completed" && (
                      <button
                        title="Make this recurring"
                        onClick={() =>
                          setCadenceSeed({ intentText: i.text, nodeId: i.targetNode })
                        }
                        className="rounded-full border border-border bg-surface px-1.5 py-0.5 text-[11px] text-ink-muted hover:border-accent hover:text-accent"
                      >
                        ↻ recur
                      </button>
                    )}
                  </span>
                  );
                })}
              </div>
            </section>

            {/* The living plan */}
            <section className="rounded-lg border border-border bg-surface p-4">
              <h2 className="mb-2 text-sm font-semibold text-ink">Living plan</h2>
              {!effectiveIntent ? (
                <EmptyState title="No intent selected">Submit or pick an intent above.</EmptyState>
              ) : plan.data ? (
                <>
                {/* F6: the submitted intent, rendered as the markdown it was written in. */}
                {plan.data.intent.text.length > 120 || plan.data.intent.text.includes("\n") ? (
                  <details className="mb-3 rounded-md border border-border bg-canvas px-3 py-2">
                    <summary className="cursor-pointer text-xs font-medium text-ink-muted">
                      Intent — {plan.data.intent.text.split("\n")[0].replace(/^#+\s*/, "").slice(0, 80)}
                    </summary>
                    <Markdown text={plan.data.intent.text} className="mt-1 text-xs text-ink" />
                  </details>
                ) : (
                  <p className="mb-3 rounded-md border border-border bg-canvas px-3 py-2 text-xs text-ink">
                    {plan.data.intent.text}
                  </p>
                )}
                {plan.data.tree.map((n) => (
                  <PlanOutline
                    key={n.assignment.id}
                    node={n}
                    nodeName={nodeName}
                    orgId={effectiveOrg}
                    onNote={(assignmentId, stageIdx, noteText) =>
                      leaveNote.mutate({
                        intentId: effectiveIntent,
                        body: {
                          text: noteText,
                          assignmentId,
                          stageIdx: stageIdx ?? undefined,
                        },
                      })
                    }
                    onIntervene={(assignmentId, note) =>
                      act.mutate({ assignmentId, action: "intervene", body: { note } })
                    }
                    onAccept={(assignmentId) =>
                      act.mutate({ assignmentId, action: "accept", body: { note: "" } })
                    }
                    onReject={(assignmentId, note) =>
                      act.mutate({ assignmentId, action: "reject", body: { note } })
                    }
                    onInspect={setInspectNode}
                  />
                ))}
                </>
              ) : (
                <CenteredSpinner label="Loading plan…" />
              )}
            </section>

            {/* Cadences: put this org on a schedule (E7) */}
            <CadenceSection
              orgId={effectiveOrg}
              nodeName={nodeName}
              seed={cadenceSeed}
              onSeedConsumed={() => setCadenceSeed(null)}
            />
          </div>

          {/* Inbox: notifications only — open gates render in the main column (F4). */}
          <aside className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-ink">Inbox</h2>
            {(notifications.data ?? []).length > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-ink-muted">While you were away</span>
                <button className="text-[11px] text-accent hover:underline"
                        onClick={() => markRead.mutate(undefined)}>
                  mark all read
                </button>
              </div>
            )}
            {(notifications.data ?? []).map((n) => (
              <div key={n.id}
                   className={`rounded-md border px-3 py-2 text-xs ${SEVERITY_TONE[n.severity]}`}>
                <span className="font-medium">{n.kind}</span> · {n.text}
              </div>
            ))}
            {(gates.data?.length ?? 0) === 0 && (notifications.data?.length ?? 0) === 0 && (
              <p className="text-xs text-ink-muted">Nothing needs you. The org is working.</p>
            )}
          </aside>
        </main>
      )}
      {inspectNode && effectiveOrg && (
        <InspectorPanel
          orgId={effectiveOrg}
          nodeId={inspectNode}
          nodeName={nodeName}
          onClose={() => setInspectNode(null)}
        />
      )}
    </div>
  );
}
