// The /execute landing (live-run finding F5): the operator picks WHICH team to drive before
// seeing any team's console. Only teams that are up and running (actuated: live or degraded)
// are offered — work can't be given to a team with no agents running. Duplicate names
// disambiguate with an id suffix (F9).
import { useQueries } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiGet } from "../../api/client";
import type { OrgSummary } from "../../api/types";
import type { Pulse } from "../../api/pulse";
import { Button, CenteredSpinner, EmptyState } from "../common";
import { pulseNarrative } from "./MissionControl";

/** Actuation states that count as "up and running" for the Execute page. */
export const RUNNING_STATES = new Set(["live", "degraded"]);

/**
 * The teams that are up and running, read off each team's pulse. ``loading`` stays true until
 * every pulse has answered once, so a running team never flickers out of the list on first paint.
 */
export function useRunningTeams(teams: OrgSummary[]) {
  const pulses = useQueries({
    queries: teams.map((o) => ({
      queryKey: ["pulse", o.id],
      queryFn: () => apiGet<Pulse>(`/teams/${o.id}/pulse`),
      staleTime: 5_000,
      // Keep the list honest as teams are actuated / deactuated elsewhere.
      refetchInterval: 5_000,
    })),
  });
  const pulseOf = new Map<string, Pulse | undefined>(
    teams.map((o, i) => [o.id, pulses[i]?.data]),
  );
  const isRunning = (id: string) => RUNNING_STATES.has(pulseOf.get(id)?.actuation?.state ?? "");
  const loading = pulses.some((q) => q.isPending);
  const running = teams.filter((o) => isRunning(o.id));
  return { running, pulseOf, loading };
}

const ACTUATION_TONE: Record<string, string> = {
  live: "bg-ok/15 text-ok",
  degraded: "bg-warn/15 text-warn",
  provisioning: "bg-warn/15 text-warn",
  draining: "bg-warn/15 text-warn",
};

/** F9: duplicate team names are indistinguishable on cards — suffix colliding names. */
export function orgLabelSuffix(teams: { id: string; name: string }[]): (id: string) => string {
  const counts = new Map<string, number>();
  for (const o of teams) counts.set(o.name, (counts.get(o.name) ?? 0) + 1);
  const byId = new Map(teams.map((o) => [o.id, o]));
  return (id: string) => {
    const o = byId.get(id);
    return o && (counts.get(o.name) ?? 0) > 1 ? `· ${o.id.slice(-5)}` : "";
  };
}

export function OrgPicker({
  teams,
  onPick,
}: {
  teams: OrgSummary[];
  onPick: (teamId: string) => void;
}) {
  const navigate = useNavigate();
  const { running, pulseOf, loading } = useRunningTeams(teams);
  const sorted = [...running].sort((a, b) => (b.updatedAt ?? "").localeCompare(a.updatedAt ?? ""));
  const suffix = orgLabelSuffix(teams);
  const idle = teams.length - running.length;

  if (teams.length === 0) {
    return <EmptyState title="No teams yet">Build one in the editor first.</EmptyState>;
  }
  if (loading && running.length === 0) {
    return <CenteredSpinner label="Finding running teams…" />;
  }
  if (running.length === 0) {
    return (
      <EmptyState
        title="No teams are running"
        action={
          <Button variant="primary" onClick={() => navigate("/actuate")}>
            Go to Actuate
          </Button>
        }
      >
        Actuate a team to give it work here.
      </EmptyState>
    );
  }
  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <h2 className="mb-1 text-sm font-semibold text-ink">Pick a team to drive</h2>
      <p className="mb-4 text-xs text-ink-muted">
        Running teams — their pulse tells you whether anything needs you.
        {idle > 0 && (
          <>
            {" "}
            {idle} other team{idle === 1 ? " isn't" : "s aren't"} running —{" "}
            <button className="text-accent hover:underline" onClick={() => navigate("/actuate")}>
              actuate
            </button>{" "}
            to drive {idle === 1 ? "it" : "them"}.
          </>
        )}
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
              }`}
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
