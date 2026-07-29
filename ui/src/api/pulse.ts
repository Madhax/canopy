// Mission control's feed (operator-experience.md §2): the org pulse header + one overlay row
// per node, one aggregate. Fresh via SSE invalidation ("pulse" key), polling fallback.
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import { usePollInterval } from "./work";

export interface PulseNode {
  nodeId: string;
  name: string;
  managerId: string | null;
  roleKey: string;
  status: string;
  current: { assignmentId: string; state: string; briefPreview: string } | null;
  queueDepth: number;
  wip: number;
  meter: { spent: number; allowance: number; warned: boolean; state: string } | null;
  openGateKinds: string[];
  runtimeKind: string;
}

export interface Pulse {
  actuation: { id: string; state: string } | null;
  intents: { open: number; total: number };
  gates: { open: number; byKind: Record<string, number>; attention: number };
  burn: {
    windowMinutes: number;
    tokensPerMinute: number;
    estCostMicrosPerHour: number;
    costsAreEstimates: boolean;
  };
  nodes: PulseNode[];
}

export function usePulse(orgId: string | null) {
  return useQuery({
    queryKey: ["pulse", orgId],
    queryFn: () => apiGet<Pulse>(`/organizations/${orgId}/pulse`),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
  });
}
