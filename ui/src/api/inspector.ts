// The agent inspector's feed (operator-experience.md §3): one aggregate for the eight tabs,
// plus memory reset and the workspace file preview. Kept fresh the same way as work.ts —
// SSE invalidations when live, polling fallback otherwise.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import { usePollInterval } from "./work";
import type { Assignment, Gate, Meter, Step } from "./work";

export interface Charter {
  displayName: string;
  roleKey: string;
  isManager: boolean;
  instructions: string;
  managerNodeId: string | null;
  reportNodeIds: string[];
  toolGrants: string[];
  defaultRuntime: string;
}

export interface ToolEvent {
  id: string;
  tool: string;
  outcome: string;
  detail: string;
  assignment_id: string | null;
  created_at: string;
}

export interface WorkspaceFile {
  path: string;
  size: number;
  modifiedAt: string;
}

export interface AgentState {
  nodeId: string;
  charter: Charter | null;
  binding: { profileId: string; name: string; provider: string; model: string } | null;
  envelope: { toolGrants: string[]; runtimeKind: string };
  salary: { perAssignmentAllowance: number; warnThresholdPct: number; hardStop: boolean };
  directory: {
    status: string;
    lastHeartbeatAt: string | null;
    heartbeatAgeSeconds: number | null;
    endpointUrl: string | null;
  } | null;
  actuation: { id: string; state: string } | null;
  stats: {
    assignmentsTotal: number;
    assignmentsDone: number;
    accepted: number;
    acceptanceRate: number | null;
    avgCostTokens: number | null;
    escalations: number;
  };
  current: {
    assignment: Assignment;
    briefs: { version: number; text: string; createdAt: string }[];
    plan: {
      stages: { idx: number; title: string; state: string; envelopeTokens: number | null }[];
    } | null;
    steps: Step[];
    meter: Meter | null;
    gates: Gate[];
  } | null;
  queue: Assignment[];
  history: (Assignment & { spentTokens: number })[];
  gates: { open: Gate[]; recent: Gate[] };
  spend: { nodeTokens: number; orgTokens: number; sharePct: number };
  memory: { seq: number; entry: Record<string, unknown>; createdAt: string }[];
  session: {
    sessionRef: string | null;
    transcriptPath: string | null;
    toolEvents: ToolEvent[];
    logTail: string[];
  };
  workspace: { root: string; files: WorkspaceFile[]; truncated: boolean } | null;
}

export interface FilePreview {
  path: string;
  size: number;
  modifiedAt: string;
  content: string | null;
  reason: "too-large" | "binary" | null;
}

export function useAgentState(teamId: string | null, nodeId: string | null) {
  return useQuery({
    queryKey: ["agent-state", teamId, nodeId],
    queryFn: () => apiGet<AgentState>(`/teams/${teamId}/agents/${nodeId}/state`),
    enabled: !!teamId && !!nodeId,
    refetchInterval: usePollInterval(),
  });
}

export function useResetMemory(teamId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (nodeId: string) =>
      apiSend("DELETE", `/teams/${teamId}/agents/${nodeId}/memory`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent-state"] }),
  });
}

export function useWorkspaceFile(
  teamId: string | null,
  nodeId: string | null,
  path: string | null,
) {
  return useQuery({
    queryKey: ["workspace-file", teamId, nodeId, path],
    queryFn: () =>
      apiGet<FilePreview>(
        `/teams/${teamId}/agents/${nodeId}/workspace/file?path=${encodeURIComponent(path!)}`,
      ),
    enabled: !!teamId && !!nodeId && !!path,
  });
}
