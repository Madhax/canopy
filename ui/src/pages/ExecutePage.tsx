// Phase 3 · Execute — the operator work surface (E5 part 1): submit intents, review the
// staged fan-out, read the living plan, and clear the inbox. Everything here is the E2/E3
// engine API; polling now, SSE in a later E5 part.
import { useMemo, useState } from "react";
import { useCatalog } from "../api/catalog";
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
import { Button, CenteredSpinner, EmptyState } from "../components/common";
import { CostSection } from "../components/execute/CostExplorer";
import { GateCard } from "../components/execute/GateCard";
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
  const [orgId, setOrgId] = useState<string | null>(null);
  const effectiveOrg = orgId ?? orgs.data?.[0]?.id ?? null;
  const [intentId, setIntentId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [view, setView] = useState<"work" | "costs">("work");

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

  const nodeName = useMemo(() => {
    const byId = new Map((orgDoc.data?.agents ?? []).map((a) => [a.id, a.name]));
    return (id: string) => byId.get(id) ?? id;
  }, [orgDoc.data]);

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
          <div className="flex rounded-md border border-border bg-canvas p-0.5 text-xs">
            {(["work", "costs"] as const).map((v) => (
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
            }}
            className="rounded-md border border-border bg-canvas px-2 py-1 text-sm outline-none focus:border-accent"
          >
            {(orgs.data ?? []).map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      {orgs.isLoading ? (
        <CenteredSpinner label="Loading organizations…" />
      ) : !effectiveOrg ? (
        <EmptyState title="No organizations yet">Build one in the editor first.</EmptyState>
      ) : view === "costs" ? (
        <main className="mx-auto max-w-6xl px-6 py-6">
          <CostSection orgId={effectiveOrg} nodeName={nodeName} />
        </main>
      ) : (
        <main className="mx-auto grid max-w-6xl grid-cols-[1fr_320px] gap-6 px-6 py-6">
          <div className="flex flex-col gap-6">
            {/* Intent console */}
            <section>
              <form
                className="mb-3 flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (text.trim()) submit.mutate({ text: text.trim() });
                  setText("");
                }}
              >
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder='Give the org work — e.g. "Add CSV export; all tests must pass"'
                  className="flex-1 rounded-md border border-border bg-canvas px-3 py-2 text-sm outline-none focus:border-accent"
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
                {(intents.data ?? []).map((i) => (
                  <button
                    key={i.id}
                    onClick={() => setIntentId(i.id)}
                    className={`rounded-full border px-3 py-1 text-xs ${
                      i.id === effectiveIntent
                        ? "border-accent bg-accent/10 text-ink"
                        : "border-border bg-surface text-ink-muted hover:border-accent"
                    }`}
                  >
                    {i.text.slice(0, 48)}
                    {i.text.length > 48 ? "…" : ""}
                    <span className="ml-1 text-[10px] uppercase">{i.state}</span>
                  </button>
                ))}
              </div>
            </section>

            {/* The living plan */}
            <section className="rounded-lg border border-border bg-surface p-4">
              <h2 className="mb-2 text-sm font-semibold text-ink">Living plan</h2>
              {!effectiveIntent ? (
                <EmptyState title="No intent selected">Submit or pick an intent above.</EmptyState>
              ) : plan.data ? (
                plan.data.tree.map((n) => (
                  <PlanOutline
                    key={n.assignment.id}
                    node={n}
                    nodeName={nodeName}
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
                  />
                ))
              ) : (
                <CenteredSpinner label="Loading plan…" />
              )}
            </section>
          </div>

          {/* Inbox: needs-you first (open operator gates), then the pulse */}
          <aside className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-ink">
              Inbox
              {(gates.data?.length ?? 0) > 0 && (
                <span className="ml-2 rounded-full bg-danger/15 px-2 py-0.5 text-[11px] text-danger">
                  {gates.data!.length} need you
                </span>
              )}
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
    </div>
  );
}
