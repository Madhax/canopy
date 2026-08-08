// The /execute landing (live-run finding F5): the operator picks WHICH org to drive before
// seeing any org's console — the old default (first org in the list, possibly unactuated)
// buried the live fleet. Actuated orgs sort first and carry their pulse narrative; the rest
// are one click from the same console. Duplicate names disambiguate with an id suffix (F9).
import { useQueries } from "@tanstack/react-query";
import { apiGet } from "../../api/client";
import type { OrgSummary } from "../../api/types";
import type { Pulse } from "../../api/pulse";
import { EmptyState } from "../common";
import { pulseNarrative } from "./MissionControl";

const ACTUATION_TONE: Record<string, string> = {
  live: "bg-ok/15 text-ok",
  degraded: "bg-warn/15 text-warn",
  provisioning: "bg-warn/15 text-warn",
  draining: "bg-warn/15 text-warn",
};

/** F9: duplicate org names are indistinguishable on cards — suffix colliding names. */
export function orgLabelSuffix(orgs: { id: string; name: string }[]): (id: string) => string {
  const counts = new Map<string, number>();
  for (const o of orgs) counts.set(o.name, (counts.get(o.name) ?? 0) + 1);
  const byId = new Map(orgs.map((o) => [o.id, o]));
  return (id: string) => {
    const o = byId.get(id);
    return o && (counts.get(o.name) ?? 0) > 1 ? `· ${o.id.slice(-5)}` : "";
  };
}

export function OrgPicker({
  orgs,
  onPick,
}: {
  orgs: OrgSummary[];
  onPick: (orgId: string) => void;
}) {
  const pulses = useQueries({
    queries: orgs.map((o) => ({
      queryKey: ["pulse", o.id],
      queryFn: () => apiGet<Pulse>(`/organizations/${o.id}/pulse`),
      staleTime: 5_000,
    })),
  });
  const pulseOf = new Map<string, Pulse | undefined>(
    orgs.map((o, i) => [o.id, pulses[i]?.data]),
  );
  const isLive = (id: string) => {
    const s = pulseOf.get(id)?.actuation?.state;
    return s === "live" || s === "degraded";
  };
  const sorted = [...orgs].sort((a, b) => {
    const la = isLive(a.id) ? 0 : 1;
    const lb = isLive(b.id) ? 0 : 1;
    if (la !== lb) return la - lb;
    return (b.updatedAt ?? "").localeCompare(a.updatedAt ?? "");
  });
  const suffix = orgLabelSuffix(orgs);

  if (orgs.length === 0) {
    return <EmptyState title="No organizations yet">Build one in the editor first.</EmptyState>;
  }
  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <h2 className="mb-1 text-sm font-semibold text-ink">Pick an organization to drive</h2>
      <p className="mb-4 text-xs text-ink-muted">
        Actuated organizations first — their pulse tells you whether anything needs you.
      </p>
      <div className="flex flex-col gap-2">
        {sorted.map((o) => {
          const pulse = pulseOf.get(o.id);
          const actuation = pulse?.actuation?.state ?? "not actuated";
          const attention = pulse?.gates.attention ?? 0;
          return (
            <button
              key={o.id}
              onClick={() => onPick(o.id)}
              className={`flex flex-wrap items-center gap-3 rounded-lg border bg-surface px-4 py-3 text-left shadow-sm transition-shadow hover:border-accent hover:shadow-md ${
                attention > 0 ? "border-danger/40" : "border-border"
              } ${isLive(o.id) ? "" : "opacity-70"}`}
            >
              <span className="text-sm font-medium text-ink">
                {o.name}
                {suffix(o.id) && (
                  <span className="ml-1.5 font-mono text-[10px] text-ink-muted">
                    {suffix(o.id)}
                  </span>
                )}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                  ACTUATION_TONE[actuation] ?? "bg-surface-2 text-ink-muted"
                }`}
              >
                {actuation}
              </span>
              <span className="text-xs text-ink-muted">
                {pulse ? pulseNarrative(pulse) : `${o.agentCount} agents`}
              </span>
              {attention > 0 && (
                <span className="ml-auto animate-pulse rounded-full bg-danger/15 px-2 py-0.5 text-[11px] font-semibold text-danger">
                  {attention} need{attention === 1 ? "s" : ""} you
                </span>
              )}
            </button>
          );
        })}
      </div>
    </main>
  );
}
