// The capacity console's single source (design/organizations/06 §8): one aggregate,
// GET /api/capacity — every number arrives computed (source tier, age, burn, runway).
// Zero capacity math lives in the UI; the console and the scheduler can never disagree.
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";

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
