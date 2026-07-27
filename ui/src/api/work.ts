// The operator work surface (E5) over the E2 engine APIs. Polling via react-query — the SSE
// channel replaces the intervals in a later E5 part; the query keys are already event-shaped.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";

export interface Assignment {
  id: string;
  nodeId: string;
  parentId: string | null;
  state: string;
  briefVersion: number;
  contractKind: string;
  contractType: string;
  meterId: string | null;
  priority: number;
  sessionRef: string | null;
  createdAt: string;
}

export interface Meter {
  id: string;
  allowance: number;
  spent: number;
  reserved: number;
  state: string;
  warned: boolean;
}

export interface Gate {
  id: string;
  assignmentId: string;
  kind: string;
  openedBy: string;
  owner: string;
  reason: string;
  payload: Record<string, unknown>;
  state: string;
  resolution: Record<string, unknown> | null;
  createdAt: string;
}

export interface WorkNote {
  id: string;
  assignmentId: string | null;
  stageIdx: number | null;
  author: string;
  text: string;
  createdAt: string;
  deliveredAt: string | null;
}

export interface PlanNode {
  assignment: Assignment;
  brief: { text: string; artifactRefs: string[]; version: number } | null;
  plan: {
    stages: {
      idx: number;
      title: string;
      state: string;
      startedAt: string | null;
      completedAt: string | null;
    }[];
  } | null;
  gates: Gate[];
  meter: Meter | null;
  notes: WorkNote[];
  children: PlanNode[];
}

export interface Intent {
  id: string;
  text: string;
  state: string;
  targetNode: string;
  createdAt: string;
  rootAssignmentId: string | null;
}

export interface Notification {
  id: string;
  severity: "attention" | "warning" | "info";
  kind: string;
  subjectIds: string[];
  text: string;
  createdAt: string;
  readAt: string | null;
}

const POLL = 2500;

export function useIntents(orgId: string | null) {
  return useQuery({
    queryKey: ["intents", orgId],
    queryFn: () => apiGet<{ intents: Intent[] }>(`/organizations/${orgId}/intents`),
    enabled: !!orgId,
    refetchInterval: POLL,
    select: (d) => d.intents,
  });
}

export function useIntentPlan(intentId: string | null) {
  return useQuery({
    queryKey: ["intent-plan", intentId],
    queryFn: () =>
      apiGet<{ intent: Intent; tree: PlanNode[]; intentNotes: WorkNote[] }>(
        `/intents/${intentId}/plan`,
      ),
    enabled: !!intentId,
    refetchInterval: POLL,
  });
}

export function useOperatorGates(orgId: string | null) {
  return useQuery({
    queryKey: ["gates", orgId],
    queryFn: () =>
      apiGet<{ gates: Gate[] }>(`/organizations/${orgId}/gates?state=open&owner=operator`),
    enabled: !!orgId,
    refetchInterval: POLL,
    select: (d) => d.gates,
  });
}

export function useNotifications(orgId: string | null) {
  return useQuery({
    queryKey: ["notifications", orgId],
    queryFn: () =>
      apiGet<{ notifications: Notification[] }>(
        `/organizations/${orgId}/notifications?unread=true`,
      ),
    enabled: !!orgId,
    refetchInterval: POLL,
    select: (d) => d.notifications,
  });
}

function useInvalidateWork(orgId: string | null) {
  const qc = useQueryClient();
  return () => {
    for (const key of ["intents", "intent-plan", "gates", "notifications", "assignments"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
    void orgId;
  };
}

export function useSubmitIntent(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (body: { text: string; targetNodeId?: string }) =>
      apiSend("POST", `/organizations/${orgId}/intents`, body),
    onSuccess: invalidate,
  });
}

export interface ResolveBody {
  action: string;
  note?: string;
  amount?: number;
  toNodeId?: string;
  answer?: string;
  brief?: string;
  assignmentId?: string;
}

export function useResolveGate(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({ gateId, body }: { gateId: string; body: ResolveBody }) =>
      apiSend("POST", `/gates/${gateId}/resolve`, body),
    onSuccess: invalidate,
  });
}

export function useAssignmentAction(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({
      assignmentId,
      action,
      body,
    }: {
      assignmentId: string;
      action: "accept" | "reject" | "intervene";
      body: { note: string; revisedBrief?: string };
    }) => apiSend("POST", `/assignments/${assignmentId}/${action}`, body),
    onSuccess: invalidate,
  });
}

export function useLeaveNote(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({
      intentId,
      body,
    }: {
      intentId: string;
      body: { text: string; assignmentId?: string; stageIdx?: number };
    }) => apiSend("POST", `/intents/${intentId}/notes`, body),
    onSuccess: invalidate,
  });
}

export function useMarkNotificationsRead(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (ids?: string[]) =>
      apiSend("POST", `/organizations/${orgId}/notifications/read`, { ids: ids ?? null }),
    onSuccess: invalidate,
  });
}
