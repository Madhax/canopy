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
  burn: Record<
    string,
    { teams: BurnBand[]; externalPpHr: number; otherOrgsPpHr?: number }
  >;
  runway: { exhaustsAt: string | null; burnPpHr?: number; basis: string; windowKey?: string } | null;
  events: CapacityEventRow[];
}

// Org economics (C5): the K7/K8 claims + the ceiling posture, computed server-side.
export interface OrgEconomics {
  weekSpendUsd: number;
  weeklyCostCeilingUsd: number | null;
  weekStartedAt: string;
  weekResetsAt: string;
  capacityShares: Record<string, number>;
  reserveWatermarkPct: Record<string, number>;
}

export interface CapacityOrgRow {
  id: string;
  key: string;
  name: string;
  economics: OrgEconomics | Record<string, never>;
}

export interface CapacityAggregate {
  enabled: boolean;
  accounts: CapacityAccount[];
  organizations: CapacityOrgRow[];
  orgId: string | null;
}

export function useCapacity(orgId?: string) {
  return useQuery({
    queryKey: ["capacity", orgId ?? null],
    queryFn: () =>
      apiGet<CapacityAggregate>(orgId ? `/capacity?orgId=${orgId}` : "/capacity"),
    refetchInterval: 5000,
  });
}

// --- The what-if strip (06 §3; C5): goal in, knob combinations out -----------
export interface WhatIfAction {
  teamId: string;
  teamName?: string;
  knob: "runState" | "maxConcurrentSessions" | "pace";
  value: unknown;
  label: string;
  freesPpHr: number;
}

export interface WhatIfSuggestion {
  actions: WhatIfAction[];
  freesPpHr: number;
  freesPp: number;
  satisfies: boolean | null;
}

export interface WhatIfResult {
  accountId: string | null;
  windowKey: string | null;
  horizonH?: number;
  horizonBasis?: string;
  neededPp: number | null;
  basis: string;
  suggestions: WhatIfSuggestion[];
}

export function useWhatIf() {
  return useMutation({
    mutationFn: (body: {
      accountId?: string;
      windowKey?: string;
      neededPp?: number;
      byTime?: string;
    }) => apiSend<WhatIfResult>("POST", "/capacity/whatif", body),
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
