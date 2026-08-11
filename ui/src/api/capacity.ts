// The capacity console's single source (design/organizations/06 §8): one aggregate,
// GET /api/capacity — every number arrives computed (source tier, age, burn, runway).
// Zero capacity math lives in the UI; the console and the scheduler can never disagree.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";

export interface CapacityWindow {
  key: string;
  kind: string;
  displayName: string;
  modelScope: string | null;
  state: "ok" | "warning" | "exhausted" | "unknown";
  utilizationPct: number | null;
  resetsAt: string | null;
  source: "provider-read" | "provider-event" | "inferred" | null;
  observedAt: string | null;
  ageS: number | null;
}

export interface BurnBand {
  teamId: string;
  teamName: string;
  orgId: string | null;
  orgKey: string | null;
  orgName: string | null;
  ppHr: number;
}

export interface CapacityEventRow {
  id: string;
  kind: string;
  windowKey: string | null;
  teamId: string | null;
  teamName: string | null;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface CapacityAccount {
  id: string;
  provider: string;
  authMode: string;
  label: string;
  planHint: string | null;
  maxConcurrentSessions: number;
  windows: CapacityWindow[];
  headlineWindow: string | null;
  burn: Record<string, { teams: BurnBand[]; externalPpHr: number }>;
  runway: { exhaustsAt: string | null; burnPpHr?: number; basis: string; windowKey?: string } | null;
  events: CapacityEventRow[];
}

export interface CapacityAggregate {
  enabled: boolean;
  accounts: CapacityAccount[];
}

export function useCapacity() {
  return useQuery({
    queryKey: ["capacity"],
    queryFn: () => apiGet<CapacityAggregate>("/capacity"),
    refetchInterval: 5000,
  });
}

// --- Team schedule: the K1–K6 knobs (design/organizations/04 §3; C4) ---------
export interface TeamSchedule {
  teamId: string;
  runState: "running" | "paused" | "drain";
  maxConcurrentSessions: number | null;
  paceChunkTurns: number | null;
  paceDelayS: number | null;
  modelTierCap: string | null;
  priority: "interactive" | "batch";
  activeHours: string | null;
  fallbackPolicy: string[];
  updatedAt: string | null;
}

export interface SchedulePredictions {
  windowKey: string | null;
  basis: string;
  pauseFreesPpHr: number;
  sessionCapFreesPpHr?: number;
  paceFreesPpHr?: number;
  paceBasis?: string;
}

export function useSchedule(teamId: string | undefined) {
  return useQuery({
    queryKey: ["team-schedule", teamId],
    queryFn: () =>
      apiGet<{ schedule: TeamSchedule; predictions: SchedulePredictions }>(
        `/teams/${teamId}/schedule`,
      ),
    enabled: !!teamId,
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, ...patch }: { teamId: string } & Partial<TeamSchedule>) =>
      apiSend<{ schedule: TeamSchedule; predictions: SchedulePredictions }>(
        "PUT",
        `/teams/${teamId}/schedule`,
        patch,
      ),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["team-schedule", vars.teamId] });
      qc.invalidateQueries({ queryKey: ["capacity"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}
